from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
import requests
import threading
import uvicorn
import random
import time
import json
import os


IP_SLAVES = os.getenv('IP_SLAVES').split(',')
HOSTNAME = os.getenv('HOSTNAME')
PID = random.randint(1000, 3000)
MY_IP = os.getenv('MY_IP')
QUEUE = []

ELECTION_STARTED = False
RESOURCE_IN_USE = False
COORDINATOR_IP = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_already_coordinator_exists():

    coordinatorExists = False
    coordinatorIPExists = None

    for slave_ip in IP_SLAVES:

        url = f'http://{slave_ip}:8000/coordinator'
        response = requests.get(url)

        json_data = response.json()

        if (json_data['COORDENADOR_IP'] != None):
            coordinatorIPExists = json_data['COORDENADOR_IP']
            coordinatorExists = True

            return coordinatorExists, coordinatorIPExists
        
    return coordinatorExists, coordinatorIPExists

@app.get("/coordinator")
def get_coordinator():

    global COORDINATOR_IP
    return {
            "COORDENADOR_IP" : COORDINATOR_IP,
    }

@app.get("/is-alive")
def is_alive() :
    return True

@app.post("/coordinator")
def set_coordinator():

    global COORDINATOR_IP

    coordinatorExists, coordinatorIPExists = verify_already_coordinator_exists()

    if (coordinatorExists):
        COORDINATOR_IP = coordinatorIPExists
        return {
            "COORDENADOR_IP" : coordinatorIPExists,
        } 
    else:
        COORDINATOR_IP = MY_IP
        return {
            "COORDENADOR_IP" : COORDINATOR_IP,
        }

@app.post("/coordinator/message")
def write_message():

    global RESOURCE_IN_USE

    if (not(RESOURCE_IN_USE)):

        RESOURCE_IN_USE = True

        with open("./data/records.txt", 'a', encoding='utf-8') as txt_file:

            new_record = f'INSTANCE : {HOSTNAME} / TIMESTAMP : {time.time()} / IP: {MY_IP} \n'

            txt_file.write(new_record)
            
            time.sleep(3)

        RESOURCE_IN_USE = False

    if (RESOURCE_IN_USE):
        return {
            "STATUS": "RECURSO EM USO."
        }


@app.get("/debug")
def get_debug():

    return {
        "RESOURCE_IN_USE" : RESOURCE_IN_USE,
        "MY_IP": MY_IP,
        "COORDENADOR_IP" : COORDINATOR_IP,
        "ELECTION_STARTED" : ELECTION_STARTED,
        "PID": PID,
        "QUEUE": QUEUE
    }

@app.post("/write/permission")
def write_permission():

    global RESOURCE_IN_USE
    global QUEUE

    if (COORDINATOR_IP == None) : 
        return {
            "STATUS": "COORDENADOR NÃO DEFINIDO."
        }

    if (COORDINATOR_IP != MY_IP) : 
        return {
            "STATUS": "NÃO SOU COORDENADOR."
        }

    if (RESOURCE_IN_USE) :

        return {
            "STATUS": "RECURSO EM USO."
        }

    if (not(RESOURCE_IN_USE) and len(QUEUE) > 0):

        RESOURCE_IN_USE = True

        url = f"http://{QUEUE[0]['SLAVE_IP']}:8000/coordinator/message"

        try :
            response = requests.post(url)
            if response.status_code == 200:
                QUEUE.pop(0)
        except :
            # QUEUE.pop(0)
            print(f"Erro ao comunicar com servidor: {QUEUE[0]['SLAVE_IP']}")

        RESOURCE_IN_USE = False

        return {
            "STATUS": "ARQUIVO ESCRITO E LIBERADO."
        }
    
    elif (len(QUEUE) == 0) :

        return {
            "STATUS": "FILA VAZIA."
        }
    

@app.post("/election/started")
def election_started() :
    global ELECTION_STARTED

    ELECTION_STARTED = True

    return {
        "IP": MY_IP,
        "PID": PID
    }

@app.post("/election/end")
def election_end(new_coordinator: dict):

    global COORDINATOR_IP
    global ELECTION_STARTED

    ELECTION_STARTED = False
    COORDINATOR_IP = new_coordinator['IP']

    return {
        "STATUS" : f"NOVO COORDENADOR: {COORDINATOR_IP}"
    }


@app.post("/election/start")
def start_election():

    global ELECTION_STARTED
    global COORDINATOR_IP

    PID_SLAVES = []

    if (not(ELECTION_STARTED)) :

        ELECTION_STARTED = True

        PID_SLAVES.append({
            "IP": MY_IP,
            "PID": PID
        })

        for IP in IP_SLAVES :

            if (IP != COORDINATOR_IP) :
                url = f'http://{IP}:8000/election/started'
                res = requests.post(url)
                PID_SLAVES.append(res.json())
        
        body = max(PID_SLAVES, key=lambda x: x['PID'])

        for IP in IP_SLAVES :

            if (IP != COORDINATOR_IP and IP != MY_IP) :

                url = f'http://{IP}:8000/election/end'
                res = requests.post(url, json.dumps(body))

        COORDINATOR_IP = body["IP"]
        ELECTION_STARTED = False

        print(f'{COORDINATOR_IP} é o novo coordenador.')

        return {
            "STATUS" : "ELEIÇÃO FINALIZADA."
        }
    else :
        return {
            "STATUS" : "ELEICAO JA INICIADA POR OUTRO SLAVE."
        }

@app.post("/coordinator/queue")
def set_queue(request: Request):

    if (COORDINATOR_IP != MY_IP) :
        return {
            "STATUS": "NÃO SOU COORDENADOR."
        }

    new_request = {
        "SLAVE_IP": request.client.host,
    }
    
    QUEUE.append(new_request)

    return {
	        "STATUS": "AGUARDANDO NA FILA.",
	        "POSITION": len(QUEUE)
    }


def run_uvicorn():
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":

    uvicorn_thread = threading.Thread(target=run_uvicorn)

    uvicorn_thread.start()

    print(f'Aguardando {MY_IP} inicializar...')

    time.sleep(10)

    while COORDINATOR_IP == None :

        time.sleep(random.randint(1, 5))

        IP_COORDINATOR_CANDIDATE =  random.choice([ip for ip in IP_SLAVES if ip != MY_IP])

        print(f'Tentando conexão com IP candidato a coordenador: http://{IP_COORDINATOR_CANDIDATE}:8000/coordinator')

        url = f'http://{IP_COORDINATOR_CANDIDATE}:8000/coordinator'

        response = requests.post(url)

        json_data = response.json()

        if response.status_code == 200:

            COORDINATOR_IP = json_data['COORDENADOR_IP']


    while True :


        if (COORDINATOR_IP != MY_IP) :

            try :

                url = f'http://{COORDINATOR_IP}:8000/is-alive'
                response = requests.get(url, timeout=3)

                url = f'http://{COORDINATOR_IP}:8000/coordinator/queue'
                response = requests.post(url)

            except: 

                print (f'{MY_IP} : INICIOU ELEICAO')

                IP_COORDINATOR_CANDIDATE =  random.choice([ip for ip in IP_SLAVES if (MY_IP != ip and COORDINATOR_IP != ip)])
                
                try :
                    url = f'http://{IP_COORDINATOR_CANDIDATE}:8000/election/start'
                    response = requests.post(url)

                    if response.status_code == 200:
                        url = f'http://{IP_COORDINATOR_CANDIDATE}:8000/coordinator'
                        response = requests.get(url)

                        json_data = response.json()

                        COORDINATOR_IP = json_data['COORDENADOR_IP']
                
                except :
                    print(f'Aguardando definicao do coordenador...')

            time.sleep(4)
                
        else :
                
            try :
                url = f'http://{COORDINATOR_IP}:8000/write/permission'
                response = requests.post(url)
                time.sleep(1)
            except :
                print(f'Coordenador {COORDINATOR_IP} falhou ao prosseguir com a fila.')