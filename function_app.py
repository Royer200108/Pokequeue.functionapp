import os
import azure.functions as func
import datetime
import json
import logging
import requests
from dotenv import load_dotenv
import pandas as pd
from azure.storage.blob import BlobServiceClient
import io
import random

app = func.FunctionApp()

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOMAIN = os.getenv("DOMAIN")
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")
STORAGE_ACCOUNT_NAME = os.getenv("STORAGE_ACCOUNT_NAME")

@app.queue_trigger(
    arg_name="azqueue", 
    queue_name="requests",
    connection="QueueAzureWebJobsStorage")

def QueueTriggerPokeReport(azqueue: func.QueueMessage):
    try:
        #Recuperamos el mensaje de la cola
        body = azqueue.get_body().decode('utf-8')
        record = json.loads(body)

        # Antes de cualquier cosa verificamos que el record tenga la estructura esperada.
        if not record:
            raise ValueError("Formato de mensaje inválido")

        #Definimos valores para el id y el sample_size
        id = record[0]["id_request"]
        sample_size = record[0]["sample_size"]
        if not id:
            raise ValueError("ID no encontrado en el mensaje")

        #Actualiza el estado de la peticion
        update_request( id, "inprogress" )

        #Obtennemos la peticion que se esta procesando
        request_info = get_request(id)

        # Tambien debemos de verificar que request_info tenga la estructura necesaria.
        if not request_info:
            raise ValueError("Información de solicitud inválida XD")
        
        #Obtenemos la cantidad de pokemones del tipo que dice la peticion (usando la pokeapi)
        real_sample_size = get_pokemon_by_type(request_info["type"])
        #Validamos el valor del sample_size
        if sample_size > 0 and sample_size < real_sample_size:
            #Obtenemos los pokemones del tipo que dice la peticion (usando la pokeapi)
            pokemons = random.sample(get_pokemons(request_info["type"]), sample_size)
        else: 
            pokemons = get_pokemons(request_info["type"])

        pokemons_completed = pokemon_data(pokemons)
        pokemon_bytes = generate_csv_blob(pokemons_completed)
        
        blob_name = f"poke_report_{id}.csv"
        upload_csv_to_blob(blob_name=blob_name, csv_data=pokemon_bytes)

        logger.info(f"Archivo {blob_name} se subió con éxito")

        completed_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{blob_name}"

        update_request( id, "completed", completed_url )
        #Alguas posibles excepciones que pueden ocurrir durante la ejecución de la función.
    except json.JSONDecodeError as e:
        logger.error(f"Error al decodificar JSON: {str(e)}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en la solicitud HTTP: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        if 'id' in locals():
            update_request(id, "failed")
        raise

def pokemon_data(pokemon_list: list) -> list:
    # Almacenaremos todos los datos que necesitamos para poder hacer un CSV mas completo.
    data = []
    
    for pokemon in pokemon_list:
        try:
            # Obtener detalles completos del Pokémon
            details = get_pokemon_details(pokemon['url'])
            
            # Almacenamos las estadísticas en un diccionario
            stats = {stat['stat']['name']: stat['base_stat'] for stat in details['stats']}
            
            # Extraemos las habilidades (solo tomareros las primeras 3)
            abilities = [ability['ability']['name'] for ability in details['abilities'][:3]]
            
            # Creamos el registro completo del Pokémon, junto a la URL y sus estadísticas.
            completed_pokemon = {
                'name': pokemon['name'],
                'url': pokemon['url'],
                'hp': stats.get('hp', 'N/A'),
                'attack': stats.get('attack', 'N/A'),
                'defense': stats.get('defense', 'N/A'),
                'special_attack': stats.get('special-attack', 'N/A'),
                'special_defense': stats.get('special-defense', 'N/A'),
                'speed': stats.get('speed', 'N/A'),
                'abilities': ', '.join(abilities) if abilities else 'N/A',
                'height': details.get('height', 'N/A'),
                'weight': details.get('weight', 'N/A')
            }
            
            data.append(completed_pokemon)
        # Manejamos excepciones si en algun momento falla.
        except Exception as e:
            logger.error(f"Error al obtener detalles para {pokemon['name']}: {str(e)}")
            # Para no dejar sin guardar el registro, guardamos los datos que ya tenemos y las estadísticas como 'Error'. 
            data.append({
                'name': pokemon['name'],
                'url': pokemon['url'],
                'hp': 'Error',
                'attack': 'Error',
                'defense': 'Error',
                'special_attack': 'Error',
                'special_defense': 'Error',
                'speed': 'Error',
                'abilities': 'Error',
                'height': 'Error',
                'weight': 'Error'
            })
    
    return data

#Aqui lo unico que hacemos es obtener la url del pokemos para asi obtener los detalles desde la API de PokeAPI.
def get_pokemon_details(url: str) -> dict:
    response = requests.get(url, timeout=3000)
    response.raise_for_status()
    return response.json()

#Funcion para actualizar el status del id que vamos a ingresar
def update_request(id: int, status: str, url: str = None) -> dict:
    payload = {
        "status": status,
        "id": id
    }

    if url:
        payload["url"] = url

    reponse = requests.put( f"{DOMAIN}/api/request", json=payload )
    return reponse.json()

#Funcion que obtiene la peticion especificada 
def get_request(id: int) -> dict:
    reponse = requests.get( f"{DOMAIN}/api/request/{id}" )
    return reponse.json()[0]

#Funcion que obtiene los pokemon para agregarlos al csv
def get_pokemons( type: str) -> dict:
    pokeapi_url = f"https://pokeapi.co/api/v2/type/{type}"

    reponse = requests.get(pokeapi_url, timeout=3000)
    data = reponse.json()
    pokemon_entries = data.get("pokemon", [])

    return [p["pokemon"] for p in pokemon_entries]

#Funcion que obtiene la cantidad de pokemon por el tipo especificado
#Esta info me sirve par validar que el sample_size sea correcto
def get_pokemon_by_type(type: str) -> int:
    pokeapi_url = f"https://pokeapi.co/api/v2/type/{type}"
    reponse = requests.get(pokeapi_url, timeout=3000)
    data = reponse.json()
    
    return len(data.get("pokemon", []))

#Funcion que genera el ficher csv
def generate_csv_blob(pokemon_list: list) -> bytes:  
    # Convierte la lista de pokemones en un DataFrame de pandas (estructura tabular).
    df = pd.DataFrame(pokemon_list)  
    
    # Crea un buffer en memoria que actúa como un archivo de texto, donde se escribirá el CSV.
    output = io.StringIO()  
    
    # Escribe el DataFrame como texto CSV dentro del buffer, sin incluir la columna de índices.
    df.to_csv(output, index=False, encoding='utf-8')  
    
    # Obtiene el contenido del buffer como string y lo convierte a bytes en formato UTF-8.
    csv_bytes = output.getvalue().encode('utf-8')  
    
    # Cierra el buffer para liberar recursos.
    output.close()  
    
    return csv_bytes  

#Funcion que se encarga de subir el ficher csv al blob storage
def upload_csv_to_blob( blob_name: str, csv_data: bytes):
    try:
        # Crea un cliente del servicio de Blob Storage utilizando la cadena de conexión.
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        
        # Crea un cliente para el contenedor específico donde se subirá el archivo CSV.
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_name)
        
        # Sube el archivo CSV al contenedor de Blob Storage.
        blob_client.upload_blob(csv_data, overwrite=True)
        
        logger.info(f"Archivo {blob_name} subido exitosamente a Azure Blob Storage.")
    except Exception as e:
        logger.error(f"Error uploading CSV to blob: {e}")
        raise