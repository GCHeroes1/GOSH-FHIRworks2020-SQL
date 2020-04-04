from collections import OrderedDict

from flask import Flask, request
import datetime as date
from datetime import datetime
import requests
import json #for debugging

app = Flask(__name__)

def generateToken(headersObject):
    CLIENT_ID = headersObject.get("CLIENT_ID")
    CLIENT_SECRET = headersObject.get("CLIENT_SECRET")
    SCOPE = headersObject.get("SCOPE")
    payload = "grant_type=client_credentials&client_id={}&client_secret={}&scope={}".format(CLIENT_ID, CLIENT_SECRET,
                                                                                            SCOPE)
    url = headersObject.get("url")
    headers = {'content-type': "application/x-www-form-urlencoded"}
    res = requests.post(url, payload, headers=headers)
    if res.status_code == 200:
        response_json = res.json()
        return response_json.get('access_token', None)
    else:
        raise Exception

def make_auth_header(access_token):
    return {'Authorization': 'Bearer {}'.format(access_token), 'Content-Type': 'application/fhir+json'}

def make_auth_headerPost(access_token):
    return {'Authorization': 'Bearer {}'.format(access_token)}

def make_auth_headerFHIRPost(access_token):
    return {'Authorization': 'Bearer {}'.format(access_token), 'Content-Type': 'application/json'}

def validateGender(answer):
    if answer.lower() == "male":
        answer = "male"
    elif answer.lower() == "female":
        answer = "female"
    else:
        answer = None
    return answer

def validateDate(answer):
    try:
        date.datetime.strptime(answer, '%Y-%m-%d')
    except ValueError:
        answer = None
    else:
        pass
    return answer

def validateInt(number):
    try:
        float(number)
    except ValueError:
        return None
    return round(float(number), 1)

def SQLFieldConstruction(argsObject):
    firstName = argsObject.get("name")
    familyName = argsObject.get("surname")
    birthdate = argsObject.get("birthdate")
    if birthdate is not None:
        birthdate = validateDate(birthdate.replace("\"", "").replace(" ", ""))
    gender = argsObject.get("gender")
    if gender is not None:
        gender = validateGender(gender.replace("\"", "").replace(" ", ""))
    communication = argsObject.get("language")
    prefix = argsObject.get("prefix")
    fields = [firstName, familyName, birthdate, gender, prefix, communication]
    for i in range(0, len(fields)):
        if fields[i] is not None:
            fields[i] = fields[i].replace("\"", "").replace(" ", "")
            if len(fields[i]) == 0:
                fields[i] = None
    return fields

def SQLQueryConstruction(querySettings, FHIR_BASE_URL):
    queryConstruction = "https://sqltofhir.azurewebsites.net/api/HttpTrigger-Java?code=mXImjGEQqBxOwpQJKRhmtYuGhFJ1N93nONRnTwJjsmOybCzOAIqpOQ%3D%3D&sqlQuery=SELECT * FROM Patient "
    columnHeaders = ["name", "family", "birthdate", "gender", "prefix", "communication"]
    flag = False
    whereFlag = True
    for i in range(0, len(querySettings)):
        if querySettings[i] is not None:
            if whereFlag:
                queryConstruction += "WHERE "
                whereFlag = False
            if i >= 1 and flag:
                queryConstruction += " AND "
            if i == 2 or i == 4 or i == 5:
                queryConstruction += columnHeaders[i] + "=\'" + querySettings[i] + "\'"
                flag = True
            else:
                queryConstruction += columnHeaders[i] + "=" + querySettings[i]
                flag = True
        else:
            if whereFlag:
                flag = False
    queryConstruction += " LIMIT 100&fhirServer=" + FHIR_BASE_URL.strip("https://")
    print("This the SQL query that has been generated: " + queryConstruction)
    return queryConstruction

def JSONResponse(query, header):
    return requests.request("GET", query, headers=header, data={}).json()

def FHIRQueryGeneration(queryInput, header):
    queryFetch = JSONResponse(queryInput, header)
    try:
        query = queryFetch["fhirQuery"]
    except Exception as e:
        query = None
    print("This is the FHIR query that has been generated: " + query)
    return query

def patientJSONParser(patientData, patientList, index):
    patientData[index + 1] = {
            "id": patientList["id"],
            "name": patientList["name"][0]["given"][0],
            "surname": patientList["name"][0]["family"],
            "gender": patientList["gender"],
            "birthdate": patientList["birthDate"],
    }
    if "deceasedDateTime" in patientList:
        patientData[index + 1]["deceased time"] = patientList["deceasedDateTime"]
    if "identifier" in patientList:
        patientData[index + 1]["social security number"] = patientList["identifier"][2]["value"]
    if "address" in patientList:
        patientData[index + 1]["address"] = {
                "line": patientList["address"][0]["line"][0],
                "city": patientList["address"][0]["city"],
                "state": patientList["address"][0]["state"],
                "country": patientList["address"][0]["country"]
        }
    if "maritalStatus" in patientList:
        patientData[index + 1]["marital status"] = patientList["maritalStatus"]["text"]
    if "communication" in patientList:
        patientData[index + 1]["communication"] = patientList["communication"][0]["language"][
            "text"]
    return patientData

def patientJSONConstruction(patientList, header):
    patientData = OrderedDict()
    j = 0
    if len(patientList) == 6:
        while True:
            for i in range(0, len(patientList["entry"])):
                patientData = patientJSONParser(patientData, patientList["entry"][i]["resource"], j)
                j += 1
            if patientList["link"][0]["relation"] != "next":
                break
            url = patientList["link"][0]["url"]
            # print("url is " + url)
            patientList = JSONResponse(url, header)
    else:
        pass
    # patientData = sorted([(key, value) for key, value in patientData.items()], key=lambda x: int(x[1].split(" ")[0]))
    return patientData
    # return json.dumps(patientData, indent=4)

def medicationQueryConstruction(ID, header, FHIR_BASE_URL):
    medicationQueryConstruction = "https://sqltofhir.azurewebsites.net/api/HttpTrigger-Java?code=mXImjGEQqBxOwpQJKRhmtYuGhFJ1N93nONR" \
                      "nTwJjsmOybCzOAIqpOQ%3D%3D&sqlQuery=SELECT * FROM MedicationRequest WHERE id=\'" + \
                      ID + "\' LIMIT 100&fhirServer=" + FHIR_BASE_URL.strip("https://")
    # print("This the SQL query that has been generated: " + medicationQueryConstruction)
    medicationQuery = FHIRQueryGeneration(medicationQueryConstruction, header)
    # print("This is the FHIR Medication query that has been generated: " + medicationQuery)
    return medicationQuery

def medicationJSONConstruction(ID, medicationQuery, header):
    medicationList = JSONResponse(medicationQuery, header)
    j = 0
    medicationData = OrderedDict()
    comparisonReference = "Patient/" + ID
    while True:
        if "entry" in medicationList:
            for i in range(0, len(medicationList["entry"])):
                if medicationList["entry"][i]["resource"]["subject"]["reference"] == comparisonReference:
                    medicationData[j+1] = {
                            "medication": medicationList["entry"][i]["resource"]["medicationCodeableConcept"]["text"],
                            "status": medicationList["entry"][i]["resource"]["status"],
                            "last updated": medicationList["entry"][i]["resource"]["meta"]["lastUpdated"],
                            "id": medicationList["entry"][i]["resource"]["id"],
                            "requester": medicationList["entry"][i]["resource"]["requester"]["display"],
                            "code": medicationList["entry"][i]["resource"]["medicationCodeableConcept"]["coding"][0]["code"]
                    }
                    j += 1
            if medicationList["link"][0]["relation"] == "next":
                url = medicationList["link"][0]["url"]
                # print("url is " + url)
                medicationList = JSONResponse(url, header)
            else:
                break
        else:
            break
    return medicationData

def conditionQueryConstruction(ID, header, FHIR_BASE_URL):
    conditionQueryConstruction = "https://sqltofhir.azurewebsites.net/api/HttpTrigger-Java?code=mXImjGEQqBxOwpQJKRhmtYuGhFJ1N93nONR" \
                      "nTwJjsmOybCzOAIqpOQ%3D%3D&sqlQuery=SELECT * FROM Condition WHERE id=\'" + \
                      ID + "\' LIMIT 100&fhirServer=" + FHIR_BASE_URL.strip("https://")
    # print("This the SQL query that has been generated: " + conditionQueryConstruction)
    conditionQuery = FHIRQueryGeneration(conditionQueryConstruction, header)
    # print("This is the FHIR condition query that has been generated: " + conditionQuery)
    return conditionQuery

def conditionJSONConstruction(ID, conditionQuery, header):
    conditionList = JSONResponse(conditionQuery, header)
    j = 0
    conditionData = OrderedDict()
    comparisonReference = "Patient/" + ID
    while True:
        if "entry" in conditionList:
            for i in range(0, len(conditionList["entry"])):
                if conditionList["entry"][i]["resource"]["subject"]["reference"] == comparisonReference:
                    conditionData[j+1] = {
                            "condition": conditionList["entry"][i]["resource"]["code"]["text"],
                            "clinical status": conditionList["entry"][i]["resource"]["clinicalStatus"]["coding"][0]["code"],
                            "last updated": conditionList["entry"][i]["resource"]["meta"]["lastUpdated"],
                            "id": conditionList["entry"][i]["resource"]["id"],
                            "verification status": conditionList["entry"][i]["resource"]["verificationStatus"]["coding"][0]["code"],
                            "onset time": conditionList["entry"][i]["resource"]["onsetDateTime"]
                    }
                    if "abatementDateTime" in conditionList["entry"][i]["resource"]:
                        conditionData[j+1]["abatement time"] = conditionList["entry"][i]["resource"]["abatementDateTime"]
                    j += 1
            if conditionList["link"][0]["relation"] == "next":
                url = conditionList["link"][0]["url"]
                # print("url is " + url)
                conditionList = JSONResponse(url, header)
            else:
                break
        else:
            break
    return conditionData

def encounterQueryConstruction(ID, header, FHIR_BASE_URL):
    encounterQueryConstruction = "https://sqltofhir.azurewebsites.net/api/HttpTrigger-Java?code=mXImjGEQqBxOwpQJKRhmtYuGhFJ1N93nONR" \
                      "nTwJjsmOybCzOAIqpOQ%3D%3D&sqlQuery=SELECT * FROM Encounter WHERE subject=\'Patient/" + \
                      ID + "\' ORDER BY date&fhirServer=" + FHIR_BASE_URL.strip("https://")
    # print("This the SQL query that has been generated: " + encounterQueryConstruction)
    encounterQuery = FHIRQueryGeneration(encounterQueryConstruction, header)
    # print("This is the FHIR encounter query that has been generated: " + encounterQuery)
    return encounterQuery.replace(':exact', '')

def encounterJSONConstruction(ID, encounterQuery, header):
    encounterList = JSONResponse(encounterQuery, header)
    encounterData = OrderedDict()
    j = 0
    while True:
        if "entry" in encounterList:
            for i in range(0, len(encounterList["entry"])):
                encounterData[j+1] = {
                        "status": encounterList["entry"][i]["resource"]["status"],
                        "last updated": encounterList["entry"][i]["resource"]["meta"]["lastUpdated"],
                        "id": encounterList["entry"][i]["resource"]["id"],
                        "encounter type": encounterList["entry"][i]["resource"]["type"][0]["text"],
                        "service provider": encounterList["entry"][i]["resource"]["serviceProvider"]["display"]
                }
                if "reasonCode" in encounterList["entry"][i]["resource"]:
                    encounterData[j+1]["reason"] = encounterList["entry"][i]["resource"]["reasonCode"][0]["coding"][0]["display"]
                if "participant" in encounterList["entry"][i]["resource"]: # only missing if theyre dead??
                    encounterData[j+1]["participant"] = encounterList["entry"][i]["resource"]["participant"][0]["individual"]["display"]
                if "period" in encounterList["entry"][i]["resource"]:
                    encounterData[j+1]["period"] = {
                        "start": encounterList["entry"][i]["resource"]["period"]["start"],
                        "end": encounterList["entry"][i]["resource"]["period"]["end"]
                    }
                j += 1
            if encounterList["link"][0]["relation"] == "next":
                url = encounterList["link"][0]["url"]
                # print("url is " + url)
                encounterList = JSONResponse(url, header)
            else:
                break
        else:
            break
    return encounterData

def observationQueryConstruction(ID, header, FHIR_BASE_URL):
    observationQueryConstruction = "https://sqltofhir.azurewebsites.net/api/HttpTrigger-Java?code=mXImjGEQqBxOwpQJKRhmtYuGhFJ1N93nONR" \
                      "nTwJjsmOybCzOAIqpOQ%3D%3D&sqlQuery=SELECT * FROM Observation WHERE subject=\'Patient/" + \
                      ID + "\' ORDER BY date&fhirServer=" + FHIR_BASE_URL.strip("https://")
    # print("This the SQL query that has been generated: " + observationQueryConstruction)
    observationQuery = FHIRQueryGeneration(observationQueryConstruction, header)
    # print("This is the FHIR observation query that has been generated: " + observationQuery)
    return observationQuery.replace(':exact', '')

def observationJSONConstruction(observationQuery, header):
    observationList = JSONResponse(observationQuery, header)
    observationData = OrderedDict()
    j = 0
    while True:
        if "entry" in observationList:
            for i in range(0, len(observationList["entry"])):
                observationData[j+1] = {
                        "id": observationList["entry"][i]["resource"]["id"],
                }
                if "category" in observationList["entry"][i]["resource"]:
                    observationData[j+1]["category"] = observationList["entry"][i]["resource"]["category"][0]["coding"][0]["display"]
                if "valueQuantity" in observationList["entry"][i]["resource"]:
                    observationData[j+1][observationList["entry"][i]["resource"]["code"]["coding"][0]["display"]] = {
                        "value": str(round(observationList["entry"][i]["resource"]["valueQuantity"]["value"], 1)),
                        "unit": observationList["entry"][i]["resource"]["valueQuantity"]["unit"]
                    }
                if "valueCodeableConcept" in observationList["entry"][i]["resource"]:
                    observationData[j+1][observationList["entry"][i]["resource"]["code"]["coding"][0]["display"]] = {
                        "text": observationList["entry"][i]["resource"]["valueCodeableConcept"]["text"]
                    }
                if "component" in observationList["entry"][i]["resource"]:
                    observationData[j+1]["blood pressure"] = {
                        "diastolic": str(round(observationList["entry"][i]["resource"]["component"][0]["valueQuantity"]["value"], 1)),
                        "systolic": str(round(observationList["entry"][i]["resource"]["component"][1]["valueQuantity"]["value"], 1)),
                        "unit": observationList["entry"][i]["resource"]["component"][1]["valueQuantity"]["unit"]
                    }
                if "issued" in observationList["entry"][i]["resource"]:
                    observationData[j+1]["issued"] = observationList["entry"][i]["resource"]["issued"]
                if "effectivePeriod" in observationList["entry"][i]["resource"]:
                    observationData[j+1]["effective period"] = {
                        "start": observationList["entry"][i]["resource"]["effectivePeriod"]["start"],
                        "end": observationList["entry"][i]["resource"]["effectivePeriod"]["end"]
                    }
                j += 1
            if observationList["link"][0]["relation"] == "next":
                url = observationList["link"][0]["url"]
                # print("url is " + url)
                observationList = JSONResponse(url, header)
            else:
                break
        else:
            break
    return observationData

def constructBloodPressureData(token, FHIR_BASE_URL, today, systolic, diastolic, ID):
    dataJSON = "{\
        \"token\": \"" + token + "\",\
        \"fhir_url\": \"" + FHIR_BASE_URL + "\",\
        \"date\": \"" + today + "\",\
        \"systolic\": " + str(systolic) + ",\
        \"diastolic\": " + str(diastolic) + ",\
        \"patient_id\": \"" + ID + "\",\
        \"type\": \"bloodpressure\"\
    }"
    return dataJSON

def constructHeartRateData(token, FHIR_BASE_URL, today, heartrate, ID):
    dataJSON = "{\
        \"token\": \"" + token + "\",\
        \"fhir_url\": \"" + FHIR_BASE_URL + "\",\
        \"date\": \"" + today + "\",\
        \"heartrate\": " + str(heartrate) + ",\
        \"patient_id\": \"" + ID + "\",\
        \"type\": \"heartrate\"\
    }"
    return dataJSON

def pushToFHIR(data, token, FHIR_BASE_URL):
    print("data constructed - " + data)
    headersPost = make_auth_headerPost(token)
    headersFHIRPost = make_auth_headerFHIRPost(token)
    FHIRObservation = requests.request("POST", "https://json-fhir-tool.azurewebsites.net/api/json-fhir-tool",
                                           data=data, headers=headersPost)#.replace("u", "")
    # print("FHIRObservation - " + str(FHIRObservation))
    # print(jsonConverter.dumps(FHIRObservation.json(), indent=4))
    observationPost = requests.request("POST", FHIR_BASE_URL + "/Observation", data=FHIRObservation,
                                       headers=headersFHIRPost)
    # print(json.dumps(observationPost.json(), indent=4))
    return observationPost.json()["id"]
    # return jsonConverter.dumps(observationPost.json(), indent=4)

@app.route('/')
def home():
    return 'Hello World'

@app.route('/test')
def test():
  return 'this is a test'

def headerProcessing(requestObject):
    headers = requestObject.headers
    FHIR_BASE_URL = headers.get("FHIR_BASE_URL")
    try:
        token = generateToken(headers)
    except Exception as e:
        token = None
    ID = requestObject.args.get("id")
    return FHIR_BASE_URL, token, ID

@app.route('/Patient', methods=["GET"])
def patients():
    FHIR_BASE_URL, token, ID = headerProcessing(request)
    if token is None:
        return "Please check that the information supplied in your header includes a correct CLIENT_ID, CLIENT_SECRET, SCOPE, FHIR_BASE_URL and url"
    if FHIR_BASE_URL is None:
        return "Please include a FHIR_BASE_URL"
    headersSQL = make_auth_header(token)
    patientList = JSONResponse(FHIR_BASE_URL + "/Patient", headersSQL)
    patientData = patientJSONConstruction(patientList, headersSQL)
    return patientData

@app.route('/Patient/<string:identifier>', methods=["GET"])
def patient(identifier):
    print(identifier)
    FHIR_BASE_URL, token, ID = headerProcessing(request)
    ID = identifier
    if token is None:
        return "Please check that the information supplied in your header includes a correct CLIENT_ID, CLIENT_SECRET, SCOPE, FHIR_BASE_URL and url"
    if FHIR_BASE_URL is None:
        return "Please include a FHIR_BASE_URL"
    headersSQL = make_auth_header(token)
    if ID is not None:
        ID = ID.replace("\"", "").replace(" ", "")
        patientVerification = JSONResponse(FHIR_BASE_URL + "/Patient/" + ID, headersSQL)
        if "issue" in patientVerification:
            return "Please enter a valid patient ID"
    else:
        return "Please supply a patient ID as a parameter"
    patientList = JSONResponse(FHIR_BASE_URL + "/Patient/" + ID, headersSQL)
    patientData = {}
    patientData = patientJSONParser(patientData, patientList, 0)
    return patientData[1]

@app.route('/patientSearch', methods=["GET"])
def patientSearch():
    FHIR_BASE_URL, token, ID = headerProcessing(request)
    if token is None:
        return "Please check that the information supplied in your header includes a correct CLIENT_ID, CLIENT_SECRET, SCOPE, FHIR_BASE_URL and url"
    if FHIR_BASE_URL is None:
        return "Please include a FHIR_BASE_URL"
    headersSQL = make_auth_header(token)
    if ID is not None:
        ID = ID.replace("\"", "").replace(" ", "")
    SQLFields = SQLFieldConstruction(request.args)
    SQLQuery = SQLQueryConstruction(SQLFields, FHIR_BASE_URL)
    FHIRSQLQuery = FHIRQueryGeneration(SQLQuery, headersSQL)
    if FHIRSQLQuery is not None:
        patientList = JSONResponse(FHIRSQLQuery, headersSQL)
        patientData = patientJSONConstruction(patientList, headersSQL)
        if ID is not None:
            try:
                return patientData[str(ID)]["id"]
            except:
                return "Out of bounds selection"
        else:
            return patientData
    else:
        return "No patients found"

@app.route('/medicationSearch', methods=["GET"])
def medicationSearch():
    FHIR_BASE_URL, token, ID = headerProcessing(request)
    if token is None:
        return "Please check that the information supplied in your header includes a correct CLIENT_ID, CLIENT_SECRET, SCOPE, FHIR_BASE_URL and url"
    if FHIR_BASE_URL is None:
        return "Please include a FHIR_BASE_URL"
    headersSQL = make_auth_header(token)
    if ID is not None:
        ID = ID.replace("\"", "").replace(" ", "")
        patientVerification = JSONResponse(FHIR_BASE_URL + "/Patient/" + ID, headersSQL)
        if "issue" in patientVerification:
            return "Please enter a valid patient ID"
    else:
        return "Please supply a patient ID as a parameter"
    medicationQuery = medicationQueryConstruction(ID, headersSQL, FHIR_BASE_URL)
    medicationData = medicationJSONConstruction(ID, medicationQuery, headersSQL)
    if len(medicationData) == 0:
        return "The patient has never been on any medication"
    else:
        return medicationData

@app.route('/conditionSearch', methods=["GET"])
def conditionSearch():
    FHIR_BASE_URL, token, ID = headerProcessing(request)
    if token is None:
        return "Please check that the information supplied in your header includes a correct CLIENT_ID, CLIENT_SECRET, SCOPE, FHIR_BASE_URL and url"
    if FHIR_BASE_URL is None:
        return "Please include a FHIR_BASE_URL"
    headersSQL = make_auth_header(token)
    if ID is not None:
        ID = ID.replace("\"", "").replace(" ", "")
        patientVerification = JSONResponse(FHIR_BASE_URL + "/Patient/" + ID, headersSQL)
        if "issue" in patientVerification:
            return "Please enter a valid patient ID"
    else:
        return "Please supply a patient ID as a parameter"
    conditionQuery = conditionQueryConstruction(ID, headersSQL, FHIR_BASE_URL)
    conditionData = conditionJSONConstruction(ID, conditionQuery, headersSQL)
    if len(conditionData) == 0:
        return "The patient has never had a condition"
    else:
        return conditionData

@app.route('/encounterSearch', methods=["GET"])
def encounterSearch():
    FHIR_BASE_URL, token, ID = headerProcessing(request)
    if token is None:
        return "Please check that the information supplied in your header includes a correct CLIENT_ID, CLIENT_SECRET, SCOPE, FHIR_BASE_URL and url"
    if FHIR_BASE_URL is None:
        return "Please include a FHIR_BASE_URL"
    headersSQL = make_auth_header(token)
    if ID is not None:
        ID = ID.replace("\"", "").replace(" ", "")
        patientVerification = JSONResponse(FHIR_BASE_URL + "/Patient/" + ID, headersSQL)
        if "issue" in patientVerification:
            return "Please enter a valid patient ID"
    else:
        return "Please supply a patient ID as a parameter"
    encounterQuery = encounterQueryConstruction(ID, headersSQL, FHIR_BASE_URL)
    encounterData = encounterJSONConstruction(ID, encounterQuery, headersSQL)
    if len(encounterData) == 0:
        return "The patient has never had an encounter"
    else:
        return encounterData

@app.route('/observationSearch', methods=["GET"])
def observationSearch():
    FHIR_BASE_URL, token, ID = headerProcessing(request)
    if token is None:
        return "Please check that the information supplied in your header includes a correct CLIENT_ID, CLIENT_SECRET, SCOPE, FHIR_BASE_URL and url"
    if FHIR_BASE_URL is None:
        return "Please include a FHIR_BASE_URL"
    headersSQL = make_auth_header(token)
    if ID is not None:
        ID = ID.replace("\"", "").replace(" ", "")
        patientVerification = JSONResponse(FHIR_BASE_URL + "/Patient/" + ID, headersSQL)
        if "issue" in patientVerification:
            return "Please enter a valid patient ID"
    else:
        return "Please supply a patient ID as a parameter"
    observationQuery = observationQueryConstruction(ID, headersSQL, FHIR_BASE_URL)
    observationData = observationJSONConstruction(observationQuery, headersSQL)
    if len(observationData) == 0:
        return "The patient has never had an observation"
    else:
        return observationData

def pushDataProcessing(requestObject):
    heartrate = requestObject.args.get("heartrate")
    systolic = requestObject.args.get("systolic")
    diastolic = requestObject.args.get("diastolic")
    if heartrate is not None:
        heartrate = validateInt(heartrate)
    if (systolic and diastolic) is not None:
        systolic = validateInt(systolic)
        diastolic = validateInt(diastolic)
    return heartrate, systolic, diastolic

@app.route('/observationRecord', methods=["POST"])
def observationPush():
    FHIR_BASE_URL, token, ID = headerProcessing(request)
    if token is None:
        return "Please check that the information supplied in your header includes a correct CLIENT_ID, CLIENT_SECRET, SCOPE, FHIR_BASE_URL and url"
    if FHIR_BASE_URL is None:
        return "Please include a FHIR_BASE_URL"
    headersSQL = make_auth_header(token)
    if ID is not None:
        ID = ID.replace("\"", "").replace(" ", "")
        patientVerification = JSONResponse(FHIR_BASE_URL + "/Patient/" + ID, headersSQL)
        if "issue" in patientVerification:
            return "Please enter a valid patient ID"
    else:
        return "Please supply a patient ID as a parameter"
    today = datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")
    heartrate, systolic, diastolic = pushDataProcessing(request)
    print(heartrate, systolic, diastolic)
    if (heartrate is None) and (systolic is not None) and (diastolic is not None):
        # if there isnt a heart rate but there is systolic and diastolic, continue with pushing blood pressure
        bloodPressureData = constructBloodPressureData(token, FHIR_BASE_URL, today, systolic, diastolic, ID)
        idBP = pushToFHIR(bloodPressureData, token, FHIR_BASE_URL)
        return "Successfully pushed, new observation ID for blood pressure is " + idBP
    elif (heartrate is not None) and ((systolic is None) or (diastolic is None)):
        # if there is a heart rate but there isnt a systloc or diastolic, continue with pushing heart rate
        heartRateData = constructHeartRateData(token, FHIR_BASE_URL, today, heartrate, ID)
        idHR = pushToFHIR(heartRateData, token, FHIR_BASE_URL)
        return "Successfully pushed, new observation ID for heart rate is " + idHR
    elif (heartrate is not None) and (systolic is not None) and (diastolic is not None):
        # if there is heart rate, systolic and diastolic, push heart rate and blood pressure
        bloodPressureData = constructBloodPressureData(token, FHIR_BASE_URL, today, systolic, diastolic, ID)
        idBP = pushToFHIR(bloodPressureData, token, FHIR_BASE_URL)
        heartRateData = constructHeartRateData(token, FHIR_BASE_URL, today, heartrate, ID)
        idHR = pushToFHIR(heartRateData, token, FHIR_BASE_URL)
        return "Successfully pushed, new observation ID for blood pressure is " + idBP + \
               ", new observation ID for heart rate is " + idHR
    else:
        return "Please check that you have entered valid values for heart rate (XX.X) or both systolic (XXX.X) and diastolic (XX.X)"
