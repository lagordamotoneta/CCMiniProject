# Favorite Artists control 

This is a project to apply control over favorite artists of a person and provides an ability of getting extra information about an artist such as album art and tracks in a record, this extra information is provided by a connection to LastFM API (https://www.last.fm/api)

## Overview

The main web application is defined in app/app.py and can be accessed through an HTML index page that provides a functionality that returns responses as son files as well as Flask tables by using an API. The  API with provide following methods:

Route | Type | Description
---|---|---
/getListFavArtistsJson | GET | Provides a list of artist that are currently saved as favorite. This information is read from a Cassandra database . Result is in Json format.
/searchFavArtistJson/{artist} | GET | Provides a search functionality to search for an artist. Name of artist need to be provided as parameter and will return the artist along with the albums that were saved as favourites. Result is in Json format.
/getListFavAlbumsJson/{artist}  | GET | Returns the albums that have been saved as favourite in the database. Name of artist need to be provided as parameter.Result is in Json format.
/insertArtistJSon/{artist}  | POST | Inserts a new favourite artist in the database. Name of artist need to be provided as parameter.Result of insert is in Json format.
/insertArtistAlbumJson/{artist}/{album} | POST |  Inserts a new favourite album for an artist in the database. Name of artist and name of album need to be provided as parameters.Result of insert is in Json format.
/removeFavArtist/{artist} | DELETE | Deletes an entire row , the artist and the albums. Name of artist and name of album need to be provided as parameters.Result of insert is in Json format.
/getAlbumArtJson/{artist}/{album} |  GET |  Returns the URL of an image that represents the art of an album (cover photo). This is powered by LastFM API. Name of artist and name of album need to be provided as parameters.Result of insert is in Json format.
/getAlbumTracksJson/{artist}/{album} | GET | Returns a list of tracks present in an album. This is powered by LastFM API. Name of artist and name of album need to be provided as parameters.Result of insert is in Json format.

 
## Deployment

The web application is designed for cloud deployment using Docker and Kubernetes technologies.

#### app.py

The main page of the API is an HTML index page. It is designed to be accessed through a brower. Couple of templates in app/templates/ were created for index and Flask tables display purposes. The app is served with Flask's built-in server. For deployment, the app is containerised and exposed on a public IP address at port 80 .


#### database

The project uses a Cassandra database that was created. This database stores persistent information of the artist. Artist name and albums. The albums column was created as a collection column that stores a list of albums. The primary key is artist name and also includes an ID column that is populated wit current time through uuid column.

#### CapeAPI

#### Setup of application.
 
In order to use this application, below points need to be performed as first step to create Cassandra database cluster. The Kubernetes configuration files are part of the main directory of the application. This application was deployed using Google Cloud.
 
 ```bash
# Cassandra Cluster commands for set up
 
gcloud config set compute/zone us-central1-b
export PROJECT_ID="$(gcloud config get-value project -q)"
gcloud container clusters create cassandra --num-nodes=3 --machine-type "n1-standard-2"
 
# Kubernetes deployment
 
kubectl create -f cassandra-peer-service.yml 
kubectl create -f cassandra-service.yml 
kubectl create -f cassandra-replication-controller.yml

# Check the pods are created

kubectl get pods -l name=cassandra

# scale to the number of replicas desired

kubectl scale rc cassandra --replicas=3

# Run below command couple of times until an external IP is listed for database. (You will see waiting for sometime)

kubectl get services
 
# Check the the rings for the database are there (below names will change) 
 
kubectl exec -it cassandra-lwfvw -- nodetool status

# create the needed database 
# log into one of the instances (again id will change)

kubectl exec -it cassandra-24bgm cqlsh

# you will be then into database prompt , run below commands to create the actual DB

CREATE KEYSPACE records WITH REPLICATION = {'class' : 'SimpleStrategy', 'replication_factor' : 1};

CREATE TABLE records.artistsAndAlbums (ID uuid, artistName text, albums list<text> ,artistNameLastFM text, PRIMARY KEY (artistName));

insert into records.artistsAndAlbums(ID,artistName,albums,artistNameLastFM) values(now(), 'Radiohead' ,['The King of Limbs','OK Computer'], 'radiohead' );

insert into records.artistsAndAlbums(ID,artistName,albums,artistNameLastFM) values(now(), 'Portishead' , [ 'Dummy','Third'],'portishead' );

#if everything is fine you should see a list of two artists

select * from records.artistsAndAlbums;

 ```
 
## Final notes.

This project was intended to be evaluated for cloud computing knowledge , most of what is presented in here is just a proof of concept. Application can be developed to achieve further functionality.

