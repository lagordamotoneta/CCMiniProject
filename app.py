from flask import Flask, render_template, request, jsonify
import json
import requests
from cassandra.cluster import Cluster
from flask_table import Table, Col
from flask import escape
import requests_cache

# we stablish a cache handling so our most used requests are kept in the server for quicker responses
requests_cache.install_cache('artists_api_cache', backend='sqlite', expire_after=36000)

#Definition of Flask tables for our responses where apply
class ResultArtists(Table):
    artistname = Col('Artist')
class ResultAlbums(Table):
   albums = Col('Albums')
class ResultArtistAlbums(Table):
    artistname = Col('Artist')
    albums = Col('Albums')

#we create connection to our cassandra DB using the created Cluster
cluster = Cluster(['cassandra'])
#cluster = Cluster(['172.18.0.2'])
session = cluster.connect()

# application config files are loaded. These are used fir example to store our api keys.
app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py')

#LastFM endpoint to be used across our application.
lastfm_album = 'http://ws.audioscrobbler.com/2.0/?method=album.getinfo&api_key={MY_API_KEY}&artist={reqArtistName}&album={reqAlbum}&format=json'

#Key provided by LastFM. This key is stored in config files so is not visible or harcoded in the code it self.
API_KEY =app.config['MY_API_KEY']

#index of the application, an HTML page
@app.route('/')
def index():
        return render_template('index.html')

######################################################################
####Applications to serve endpoints in URL and return Json results#####
######################################################################

# SEARCH A FAVORITE ARTIST AND FAVORITE ALBUMS BY NAME SEARCH
# By using Cassandra database, a user can obtain a list of favorite artists 
# nad favorite albums associated to it from persistent information stored at database
        
@app.route('/searchFavArtistJson/<artist>',  methods=['GET'])
def searchFavArtistJson(artist):
    artist = artist
    querystm = 'SELECT artistname,albums FROM records.artistsAndAlbums where artistname=\''+ artist+'\'' + ' ALLOW FILTERING'
    rows = session.execute(querystm)
    #in here as in below parts, we need to handle the response sent by Cassandra DB
    #in order to process it
    rowList=list(rows)
    for row in rowList:
        if row.albums is None:
            return (jsonify({"status":"error"},{"message":"no artist found"}),40)
        else:
            return jsonify({"result":{"artist":row.artistname ,"albums":row.albums}}),200

# GET A LIST OF ALL FAVORITE ARTISTS
# By using Cassandra database, a user can obtain a list of favorite artists 
# from persistent information stored at database

@app.route('/getListFavArtistsJson',  methods=['GET'])
def getListFavArtistsJson():
    rows = session.execute('SELECT artistname FROM records.artistsAndAlbums')
    response=[]
    for row in rows:
        response.append(row.artistname)
    if len(response)>1:
        return (jsonify({"artists":response}),200)
    else:
        return jsonify({"status":"error"},{"message":"no artist found"}),404

# GET FAVORITE ALBUMS FROM A FAVORITE ARTIST
# By using Cassandra database, a user can add a new favorite album for an 
# existing artist and get the value stored as persistent information 

@app.route('/getListFavAlbumsJson/<artist>',  methods=['GET'])
def getListFavArtistAlbumsJson(artist):
    querystm = 'SELECT albums FROM records.artistsAndAlbums where artistname=\''+ artist+'\'' + ' ALLOW FILTERING'
    rows = session.execute(querystm)
    rowList=list(rows)
    for row in rows:
        if row.albums is None:
            return (jsonify({"status":"error"},{"message":"no artist found"}),404)
    return jsonify({"albums":rowList}),200

# ADD A NEW ARTIST
# By using Cassandra database, a user can add a new favorite artist 
# and get the value stored as persistent information 

@app.route('/insertArtistJSon/<artist>', methods=['GET','POST'])
def insertArtistJson(artist):
    #In thsi query statment let's observe the IF NOT EXISTS clause in Cassandra
    #which handles situations in where the records is present in database, so it
    #will insert only if the record does not exists.
    querystm = 'INSERT INTO records.artistsAndAlbums (id, artistname) VALUES (now(),\''+artist+'\') IF NOT EXISTS'
    rows = session.execute(querystm)    
    for row in rows:
        if row.applied:
            return jsonify({"status":"success"},{"message":"Artist inserted"}),201
        else:
            return jsonify({"status":"error"},{"message":"No records inderted,either artist already exists or DB error ocurred"}),409
# ADD A NEW ALBUM
# By using Cassandra database, a user can add a new favorite album of an artist 
# and get the value stored as persistent information             
@app.route('/insertArtistAlbumJson/<artistname>/<album>', methods=['GET','POST'])
def insertArtistAlbumJson(artistname,album):
    v_artist=artistname
    v_album=album
    # Let's observe the update statement below in where a column taht stores a record ,
    # in this case a list, is being uopdated by adding a new element in the list.
    querystm = 'UPDATE records.artistsAndAlbums SET albums= [\''+v_album+'\']+ albums where artistname=\''+v_artist+'\''
    rows = session.execute(querystm)
    rowList=list(rows)
    return ("<h1>Album inserted!</h1>",200)

# DELETE A FAVORITE ARTIST (WITH ITS ALBUMS)
# By using Cassandra database, a user can delete a favorite artist 
# and get the value removed from persistent information 
@app.route('/removeFavArtist/<artistname>', methods=['GET','DELETE'])
def removeFavArtistAlt(artistname):
    querystm = 'DELETE from  records.artistsAndAlbums where artistname=\''+artistname+'\''
    rows = session.execute(querystm)
    return (jsonify({"status":"sucess"},{"message":"record deleted"}),200)

# GET ALBUM ART FROM LASTFM
# By using LastFM API services, we will obtain the album art related to an artist
# There will be a call to LastFM service ONLY if the artist and album is part of 
# user's stored informatiom about their favorite artist and albums at the database 

@app.route('/getAlbumArtJson/<artistname>/<album>',  methods=['GET'])
def getAlbumArtJson(artistname, album):
    
    # we get the parameters from the application call. 
    v_ArtistName = artistname
    v_Album = album

    # We proceed to build the query that will run to determnine whether de artist 
    # and album provided are in the database (have been set as favorites by a user).
    # Let's observe the query statement below that ois filtering over a column that 
    # stores a collection of albums in this case a list.
    querystm = 'select count(*) from records.artistsAndAlbums where artistname=\''+ v_ArtistName+'\'and albums CONTAINS \''+v_Album+'\'  ALLOW FILTERING'
    rows = session.execute(querystm)
    rowList=list(rows)
    for row in rowList:
        #only if there was a record found we proceed to call LastFm's API.
        if row.count>0:
            albumArtURL=lastfm_album.format(MY_API_KEY=API_KEY,reqArtistName=v_ArtistName,reqAlbum=v_Album )
            resp=requests.get(albumArtURL)
            jsonThing=resp.json()
            #response from LastFM is a json response. 
            if resp.ok:
                #in here , the json response is parsed. In the response, the number 3 means that we will be selectin the "large" image url  
                #as is available in various sizes. Finally text is the json part having the image url information which 
                #we display later on.
                imageURL=jsonThing['album']['image'][3]['#text'] 
                #return ("<img src={imgurl}>".format(imgurl=imageURL))
                return (jsonify({"albumArtURL":imageURL}))
        else:
            return (jsonify({"error":"No saved favorite artist albums with that info</>"}))

# GET TRACKS OF AN ALBUM FROM LASTFM
# By using LastFM API services, we will obtain the tracks related to an artist's
# album. There will be a call to LastFM service ONLY if the artist and album is part of 
# user's stored informatiom about their favorite artist and albums at the database 

@app.route('/getAlbumTracksJson/<artistname>/<album>',  methods=['GET'])
def getAlbumTracksJson(artistname, album):
    v_ArtistName = artistname
    v_Album = album
    # We proceed to build the query that will run to determnine whether de artist 
    # and album provided are in the database (have been set as favorites by a user).
    # Let's observe the query statement below that ois filtering over a column that 
    # stores a collection of albums in this case a list.
    querystm = 'select count(*) from records.artistsAndAlbums where artistname=\''+ v_ArtistName+'\'and albums CONTAINS \''+v_Album+'\'  ALLOW FILTERING'
    rows = session.execute(querystm)
    rowList=list(rows)
    for row in rowList:
        #only if there was a record found we proceed to call LastFm's API.
        if row.count>0:
            albumTracks=lastfm_album.format(MY_API_KEY=API_KEY,reqArtistName=v_ArtistName,reqAlbum=v_Album)
            resp=requests.get(albumTracks)
            jsonThing=resp.json()
            tracks=jsonThing['album']['tracks']['track']

            #response from LastFM is a json response. 
            if resp.ok:
                tracks=jsonThing['album']['tracks']['track']
                i=0
                response={}
                # in here , the json response is parsed. In the response, each track is an index of a json list
                # we need to loop thru it in order to obtain the actual name of the track.  
                # the result of parsing is stored in a dictionary for later on send the response in json format.
                for track in tracks:
                    response[i] = tracks[i]['name']
                    i+=1
                return jsonify({"tracks":response}),200
            else:
                return (resp.reason, 404)
        else:
            return jsonify({"error":"No saved favorite artist albums with that info</>"}),404

##############################################################################################################
####Applications to serve requests to return Flask Tables####################################################
####(which is the same functionality as endpoints)
#############################################################################################################

# GET A LIST OF ALL FAVORITE ARTISTS
# By using Cassandra database, a user can obtain a list of favorite artists 
# from persistent information stored at database
@app.route('/getListFavArtists',  methods=['GET'])
def getListFavArtists():
    rows = session.execute('SELECT artistname FROM records.artistsAndAlbums')
    table = ResultArtists(rows)
    table.border = True
    if bool(rows):
        return render_template('resultsFavArtistsAll.html', table=table) 
    else:
        return ("<h1>No rows please hit back button</>")
   
# GET FAVORITE ALBUMS FROM A FAVORITE ARTIST
# By using Cassandra database, a user can add a new favorite album for an 
# existing artist and get the value stored as persistent information 
@app.route('/getListFavAlbums',  methods=['GET'])
def getListFavArtistAlbums():
    artist = str(request.args["artistname"])
    querystm = 'SELECT albums FROM records.artistsAndAlbums where artistname=\''+ artist+'\'' + ' ALLOW FILTERING'
    rows = session.execute(querystm)
    rowList=list(rows)
    for row in rowList:
        if row.albums is None:
            return ("<h1>There are no favorite albums for this artist! Please hit back button!</h1>")            
    table = ResultAlbums(rowList)
    table.border = True
    return render_template('resultsFavArtistsAll.html',table=table)

# SEARCH A FAVORITE ARTIST AND FAVORITE ALBUMS BY NAME SEARCH
# By using Cassandra database, a user can obtain a list of favorite artists 
# nad favorite albums associated to it from persistent information stored at database
@app.route('/searchFavArtist',  methods=['GET'])
def searchFavArtist():
    artist = str(request.args["artistname"])
    querystm = 'SELECT artistname,albums FROM records.artistsAndAlbums where artistname=\''+ artist+'\'' + ' ALLOW FILTERING'
    rows = session.execute(querystm)
    rowList=list(rows)
    table=ResultArtistAlbums(rowList)
    for row in rowList:
        if row.albums is None or row.albums is None :
            return ("<h1>There is no favorite artist saved or there are no favorite albums for this artist! Please hit back button!</h1>")
    table.border = True
    return render_template('resultsFavArtistsAll.html',table=table)

# ADD A NEW ARTIST
# By using Cassandra database, a user can add a new favorite artist 
# and get the value stored as persistent information 

@app.route('/insertArtist', methods=['POST'])
def insertArtist():
    artist=request.form["artistname"]
    querystm = 'INSERT INTO records.artistsAndAlbums (id, artistname) VALUES (now(),\''+artist+'\') IF NOT EXISTS'
    rows = session.execute(querystm)    
    for row in rows:
        if row.applied:
            return ("<h1>Artist inserted!</h1>",200)
        else:
            #in this return statement let's observe the status 409 which corresponds to conflict as the artist already exists.
            return ("<h1>Not inserted, either artist already exists or DB error ocurred</h1>",409)

# ADD A NEW ALBUM
# By using Cassandra database, a user can add a new favorite album of an artist 
# and get the value stored as persistent information  

@app.route('/insertArtistAlbum', methods=['POST'])
def insertArtistAlbum():
    artist=request.form["artistname"]
    album=request.form["album"]
    querystm = 'UPDATE records.artistsAndAlbums SET albums= [\''+album+'\']+ albums where artistname=\''+artist+'\''
    rows = session.execute(querystm)
    rowList=list(rows)
    return ("<h1>Album inserted!</h1>",200)

# DELETE A FAVORITE ARTIST (WITH ITS ALBUMS)
# By using Cassandra database, a user can delete a favorite artist 
# and get the value removed from persistent information 

@app.route('/removeFavArtist', methods=['GET','DELETE'])
def removeFavArtist():
    artist = str(request.args["artistname"])
    querystm = 'DELETE FROM records.artistsAndAlbums where artistname=\''+artist+'\''
    rows = session.execute(querystm)
    return ("<h1>Artist deleted!</>")

# GET ALBUM ART FROM LASTFM
# By using LastFM API services, we will obtain the album art related to an artist
# There will be a call to LastFM service ONLY if the artist and album is part of 
# user's stored informatiom about their favorite artist and albums at the database 

@app.route('/albumArt',  methods=['GET'])
def getAlbumArt():
    v_ArtistName=request.args["artistname"]
    v_Album=request.args["album"]
    # We proceed to build the query that will run to determnine whether de artist 
    # and album provided are in the database (have been set as favorites by a user).
    # Let's observe the query statement below that ois filtering over a column that 
    # stores a collection of albums in this case a list.
    querystm = 'select count(*) from records.artistsAndAlbums where artistname=\''+ v_ArtistName+'\'and albums CONTAINS \''+v_Album+'\'  ALLOW FILTERING'
    rows = session.execute(querystm)
    rowList=list(rows)
    for row in rowList:
        #only if there was a record found we proceed to call LastFm's API.
        if row.count>0:

            albumArtURL=lastfm_album.format(MY_API_KEY=API_KEY,reqArtistName=v_ArtistName,reqAlbum=v_Album )
            resp=requests.get(albumArtURL)
            jsonThing=resp.json()

            #response from LastFM is a json response. 
            if resp.ok:
                #in here , the json response is parsed. In the response, the number 3 means that we will be selectin the "large" image url  
                #as is available in various sizes. Finally text is the json part having the image url information which 
                #we display later on.
                imageURL=jsonThing['album']['image'][3]['#text'] 
                #return ("<img src={imgurl}>".format(imgurl=imageURL))
                return ("<img src={imgurl}>".format(imgurl=imageURL))
        else:
            return ("<h1>No saved favorite artist albums with that info</>")


# GET TRACKS OF AN ALBUM FROM LASTFM
# By using LastFM API services, we will obtain the tracks related to an artist's
# album. There will be a call to LastFM service ONLY if the artist and album is part of 
# user's stored informatiom about their favorite artist and albums at the database 

@app.route('/getAlbumTracks',  methods=['GET'])
def getAlbumTracks():
    v_ArtistName=request.args["artistname"]
    v_Album=request.args["album"]

    # We proceed to build the query that will run to determnine whether de artist 
    # and album provided are in the database (have been set as favorites by a user).
    # Let's observe the query statement below that ois filtering over a column that 
    # stores a collection of albums in this case a list.
    querystm = 'select count(*) from records.artistsAndAlbums where artistname=\''+ v_ArtistName+'\'and albums CONTAINS \''+v_Album+'\'  ALLOW FILTERING'
    rows = session.execute(querystm)
    rowList=list(rows)
    for row in rowList:
        #only if there was a record found we proceed to call LastFm's API.
        if row.count>0:
            albumTracks=lastfm_album.format(MY_API_KEY=API_KEY,reqArtistName=request.args["artistname"],reqAlbum=request.args["album"] )
            resp=requests.get(albumTracks)
            jsonThing=resp.json()
            tracks=jsonThing['album']['tracks']['track']

            #response from LastFM is a json response. 
            if resp.ok:
                tracks=jsonThing['album']['tracks']['track']
                i=0
                response={}
                # in here , the json response is parsed. In the response, each track is an index of a json list
                # we need to loop thru it in order to obtain the actual name of the track.  
                # the result of parsing is stored in a dictionary for later on send the response in json format.
                for track in tracks:
                    response[i] = tracks[i]['name']
                    i+=1
                return jsonify({"tracks":response}),200
            else:
                return (resp.reason, 404)
        else:
            return ("<h1>No saved favorite artist albums with that info</>")

if __name__=="__main__":
    app.run(host='0.0.0.0', port=8080)
