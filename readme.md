# Function App
En este repositorio se encuentra el código fuente de la Function App utilizada para generar reportes en formato de ficheros csv a partir de los mensajes extraídos del Queue Storage de Azure.

# ¿Qué herramientas y tecnologías utiliza?

* Python 3.11.8: Como lenguaje principal.
* pyenv: Como un gestor de versiones de python
* Azure Function App: Como alojamiento para este proceso serverless. 

## ¿Cómo configurar el ambiente virtual para correr el proyecto en local?

___Observación.___ Para poder configurar el ambiente virtual es necesario contar previamente con pyenv instalado.

1. Instalación de pyhton 3.10
    ```bash
    pyenv install 3.11.8
    ```

2. Creación del ambiente virtual
    ```bash
    pyenv virtualenv 3.13.1 nombre_entorno
    ```

3. Activación del ambiente virtual
    ```bash
    pyenv activate nombre_entorno
    ```

4. Instalar todas las dependencias de Python especificadas en el fichero "requirements.txt" usando pip:
    ```bash
    pip install nombre_dependencia
    ```

## ¿Cómo crear una Function App?


### Agregar el Core de las Function App (Instrucciones para un SO base Debian)

1. Paso 1.

Primero, se configura el repositorio de paquetes de Microsoft.

```bash
    wget -q https://packages.microsoft.comconfig/ubuntu/22.04/packages-microsoft-prod.deb

    sudo dpkg -i packages-microsoft-prod.deb
```

2. Paso 2.

Se actualiza el repositorio de paquetes de Microsoft.

``` bash
    sudo apt update 
```

3. Paso 3.

Se instala el paquete de las Core Tool (en este caso son las de la version 4).

```bash
    sudo apt-get install azure-functions-core-tools-4
```

### Crear la Function App

1. Ubicarse en la ubicación donde se creará la Function App desde la consola.

2. Ejecutar el comando:

```bash
    func init directorio --python
```
Que creará un nuevo directorio donde se creará la estructura necesaria para la Function App.

3. Cambiar a ese directorio.

```bash
    cd directorio
```

4. Iniciar el repositorio de github

```bash
    git init
```

5. Agregar la función que se utilizará para interactuar con la Function App.

```bash
    func new --name nombre
```

Para este caso se utilizará la opción 10 (Queue Trigger).

6. Ingresar el nombre de la cola que levantamos en azure y el "connection string" (puede ponerse cualquier cosa y luego se configura correctamente).

    * El "connection string" se obtiene del Storage Account (es la clave de acceso "key1") se debe agregar en un fichero llamado "local.setting.json" y que debe encontrase en la raíz del proyecto.
    * Por defecto el fichero tiene la variable "AzureWebJobsStorage" para definir el string de conexión, es mejor cambiar el nombre (a "QueueAzureWebJobsStorage" por ejemplo) ya que la variable original ya está siendo usada en las variables de entorno del recurso que está levantado en azure.

7. Hacer todas las configuraciones necesarias.

8. Para poder probar la función de forma local, ejecutar en consola:

```bash
    func start
```

## Desplegar la Function App a Azure

___Observación.___ Agregar la nueva variable de entorno creada en la definición de la function app en recurso_function_app/Configuración/"Variables de entorno"
`
"QueueAzureWebJobsStorage":'valor del string de conexión'
`
___Observación.___ Para poder realizar este proceso es necesario contar previamente con azure cli instalado.

1. Iniciar sesión con la cuenta de azure en la consola ubicada en el directorio donde esta la function app y seleccionar la suscripción donde está levantado el recurso.

```bash
    az login
```

2. Escribir el siguiente comando en consola:

```bash
    func azure functionapp publish nombre_recurso_functionapp
```