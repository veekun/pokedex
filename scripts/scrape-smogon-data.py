# Simple, stupid, run-and-done script
# Scrape, gather, and clean competitive moveset data from Smogon
# Saves results to a CSV file in /pokedex/data/csv/smogon_movesets.csv
# Requires requests, more info here: https://docs.python-requests.org/en/latest/

import csv, requests, json
from datetime import datetime, timedelta
from multiprocessing import pool
from time import time

# Modify these as-needed
gens = ["rb", "gs", "rs", "dp", "bw", "xy", "sm", "ss"]
path = "../pokedex/data/csv/smogon_movesets.csv"

def getPkmnNames(gen):
    if not isinstance(gen, str) or not gen in gens:
        raise TypeError("Invalid generation provided")
    else:
        r = requests.get("https://smogon.com/dex/{}/pokemon".format(gen))
        htmlString = r.text

        htmlString = htmlString[htmlString.find("dexSettings"):].split("\n")[0][14:]
        fullData = json.loads(htmlString)["injectRpcs"][1][1]["pokemon"]

        names = [entry["name"] for entry in fullData]

        return names

def getStrategies(gen, pokemon):
    if not isinstance(gen, str):
        raise TypeError("Invalid generation provided")
    elif not gen in gens:
        raise ValueError("Invalid generation provided")
    elif not isinstance(pokemon, str):
        raise TypeError("Invalid generation provided")
    else:
        r = requests.get("https://smogon.com/dex/{0}/pokemon/{1}/".format(gen, pokemon), timeout=10)
        htmlString = r.text
        htmlString = htmlString[htmlString.find("dexSettings"):].split("\n")[0][14:]
        return [gen, json.loads(htmlString)["injectRpcs"][2][1]["strategies"]]

def flattenData(stratDict):
    flatData = []
    for pkmnName in stratDict.keys():
        for gen in stratDict[pkmnName].keys():
            for format in stratDict[pkmnName][gen]:
                for moveset in format["movesets"]:
                    row = [pkmnName,
                           gen,
                           format["format"],
                           format["overview"],
                           format["comments"]]
                    for key in moveset.keys():
                        if key in ["levels", "abilities", "items", "natures"]:
                            itemString = ""
                            for entry in moveset[key]:
                                itemString = itemString + "{}".format(entry) + ", "
                            if len(itemString) > 0:
                                itemString = itemString[0:len(itemString) - 2]
                            row.append(itemString)
                        elif key == "moveslots":
                            for moveslot in moveset[key]:
                                itemString = ""
                                for move in moveslot:
                                    itemString = itemString + "{}".format(move["move"])
                                    if not move["type"] == None:
                                        itemString = itemString + " ({})".format(move["type"])
                                    itemString = itemString + "/"
                                if len(itemString) > 0:
                                    itemString = itemString[0:len(itemString) - 1]
                                row.append(itemString)
                        elif key in ["evconfigs", "ivconfigs"]:
                            itemString = ""
                            for item in moveset[key]:
                                for stat in item.keys():
                                    itemString = itemString + "{}".format(item[stat]) + "/"
                                if len(itemString) > 0:
                                    itemString = itemString[0:len(itemString) - 1]
                                itemString = itemString + ", "
                            if len(itemString) > 0:
                                itemString = itemString[0:len(itemString) - 2]
                            row.append(itemString)
                        else:
                            row.append(moveset[key])
                    itemString = ""
                    for item in format["credits"]["teams"]:
                        itemString = itemString + "{}:\n".format(item["name"])
                        for member in item["members"]:
                            if len(member.keys()) == 0:
                                continue
                            itemString = itemString + "- {0}".format(member["username"])
                            if "user_id" in member.keys():
                                itemString = itemString + " (User ID: {})".format(member['user_id'])
                            itemString = itemString + "\n"
                    itemString = itemString[0:len(itemString) - 1]
                    row.append(itemString)
                    itemString = ""
                    for member in format["credits"]["writtenBy"]:
                        itemString = itemString + "- {0}".format(member["username"])
                        if "user_id" in member.keys():
                            itemString = itemString + " (User ID: {})".format(member['user_id'])
                        itemString = itemString + "\n"
                    itemString = itemString[0:len(itemString) - 1]
                    row.append(itemString)
                    flatData.append(row)
    return flatData

def main():
    stratDict = {}
    procs = []
    p = pool.Pool()
    print("The following generations are enabled for collection:")
    print(gens)
    print("Process pool created, gathering Pokemon names from Smogon...")
    startTime = time()
    print("Data collection started at {}".format(datetime.fromtimestamp(startTime)))
    try:
        for gen in gens:
            for pokemonName in getPkmnNames(gen):
                if not pokemonName in stratDict.keys():
                        stratDict[pokemonName] = {}
                procs.append([pokemonName, p.apply_async(getStrategies, (gen, pokemonName))])
    except Exception as e:
        print("An error occurred during the setup process.\n" +
              "This likely means that the Smogon servers were unreachable in some way. " +
              "For more information, please consult the exception below:")
        print(e)
        print("The program will now close.")
        return -1
    p.close()
    print("Names gathered, process pool closed.")
    print("Gathering strategy data from Smogon...")
    numComplete = sum(proc[1].ready() for proc in procs)
    while numComplete == 0:
        numComplete = sum(proc[1].ready() for proc in procs)
    numProcs = len(procs)
    while numComplete < numProcs:
        for proc in procs:
            if proc[1].ready():
                try:
                    proc[1].get()
                except Exception as e:
                    print("A network error has occurred.\n" +
                          "Typically, this means one of the following:\n" +
                          "1) Your internet connection was lost\n" +
                          "2) The Smogon servers could not be reached in time\n" +
                          "3) There is an issue with either your network or DNS that is preventing you from downloading the target webpage.\n" +
                          "The exception details are shown below:")
                    print(e)
                    print("The program will now close.")
                    return -1
        timePerProc = (time() - startTime)/numComplete
        estTimeLeft = timePerProc * (numProcs - numComplete)
        print("{0}/{1} processes complete, estimated remaining time: {2}".format(numComplete,
                                                                                 numProcs,
                                                                                 timedelta(seconds=estTimeLeft)),
              end='\r')
        numComplete = sum(proc[1].ready() for proc in procs)
    p.join()
    print("All download processes complete, process pool joined at {}".format(datetime.fromtimestamp(time())))
    print("Adding data to strategy dictionary...")
    for proc in procs:
        stratDict[proc[0]][proc[1].get()[0]] = proc[1].get()[1]
    print("Data added to strategy dictionary.")
    print("\"Flattening\" data...")
    flatData = flattenData(stratDict)
    print("Data flattened.")
    print("Checking for suspicious rows...")
    for row in flatData:
        for item in row:
            if not type(item) in (str, bool, int, float):
                print("The following row contains data which may cause errors during CSV conversion:")
                print(row)
                print("Acceptable data types are str, bool, int, or float. Anything else may cause errors when using the data.")
                shouldCont = input("If you would like to proceed with the conversion anyways, enter \"y\" to continue: ")
                if not shouldCont == "y":
                    print("Conversion cancelled.")
                    return -1
    print("All rows passed.")
    print("Opening CSV file...")
    with open(path, "w+") as destination:
        print("CSV file opened successfully, writing data...")
        writer = csv.writer(destination)
        header = ["name",
                  "gen",
                  "format",
                  "overview",
                  "comments",
                  "set name",
                  "pokemon",
                  "shiny",
                  "gender",
                  "levels",
                  "description",
                  "abilities",
                  "items",
                  "move 1",
                  "move 2",
                  "move 3",
                  "move 4",
                  "ev configs",
                  "iv configs",
                  "natures",
                  "writing teams",
                  "Written by"]
        writer.writerow(header)
        for row in flatData:
            writer.writerow(row)
        print("All rows written, closing file...")
        destination.close()
    print("Data saved successfully.")
    return 0


if __name__ == "__main__":
    main()