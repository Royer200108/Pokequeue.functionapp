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
    body = azqueue.get_body().decode('utf-8')
    record = json.loads(body)

    id = record[0]["id_request"]
    update_request( id, "inprogress" )

    requests = get_request(id)
    pokemons = get_pokemons(requests["type"])

    #logger.info(pokemons)

    pokemon_bytes = generate_csv_blob(pokemons)
    blob_name = f"poke_report_{id}.csv"
    upload_csv_to_blob(blob_name=blob_name, csv_data=pokemon_bytes)

    completed_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{blob_name}"

    update_request( id, "completed", completed_url )

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

def get_request(id: int) -> dict:
    reponse = requests.get( f"{DOMAIN}/api/request/{id}" )
    return reponse.json()[0]

def get_pokemons( type: str) -> dict:
    pokeapi_url = f"https://pokeapi.co/api/v2/type/{type}"

    reponse = requests.get(pokeapi_url, timeout=3000)
    data = reponse.json()
    pokemon_entries = data.get("pokemon", [])

    return [p["pokemon"] for p in pokemon_entries]

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