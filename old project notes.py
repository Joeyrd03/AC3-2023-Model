import numpy as np
import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import core_functions as cf


'''Settings of the problem, If underlying assumptions change, change parameters here'''

#general settings
fuel_cost_per_mile = 15/1.151 #15$ per nautical mile and 1 mile is approximately 1.151 mile
max_center = 3 #number of maximum supply bases to be set up
year_num = 5 #number of year to maintain the base
marine_num = 2000 #number of marines we are supporting
day_num = 30 #number of days for which the interested amount of supplies is sufficient for operation
day_to_site = 3 #number of days in which supplies must be transported from base to conflict-site
supplier_base_rela = "Y" #this is either Y or N. If Y -> include transportation cost from suppliers to base. otherwise, it is ignored
base_setup_cost = "N" #this is either Y or N. If Y -> set up + maintainence cost will be include, otherwise, set up cost + maintainence cost will not be included
base_cap = "Y" #this is either Y or N. If Y -> there is a predetermined capacity for each base as provided in the excel file
#in case there is no base_cap but we want each base not to have more than a% of the total supplies, input the fraction below (value bw 0 and 1)
alpha = 0.75

#shipping information
ship_speed = 40 #miles per hour
ship_capacity = 130*2240 #130 long tons * 2240 lbs/long ton


#daily supplies needed. note: other than food_water_daily which is per person per day, all other ..._daily are quantity for the WHOLE team daily.
food_water_daily = 60 #pounds
avian_fuel_daily = 179496 #pounds
ground_fuel_daily = 316.48*6.7 #gallon*pound/gallon
ordnance_daily = 21144 #pounds


'''Pre-calculation'''
#total weight of the amount of supplies needed = water food enough for all marines (marine_num) in day_num days
# + other supplies for the mentioned duration
total_supply = food_water_daily*marine_num*day_num + (avian_fuel_daily+ground_fuel_daily+ordnance_daily)*day_num
print(f"The total amount of supplies to be stored weighs {total_supply} lbs.")
print(f"With the current ship capacity, the amount of supplies needed for {day_num}-day operation requires {total_supply/ship_capacity} shipments.")

supply_per_shipment = 1500

#loading data prepared in excel files
suppliers = pd.read_excel("~/Desktop/BlacknRossi2/data/final_model_data/suppliers.xlsx")
bases = pd.read_excel("~/Desktop/BlacknRossi2/data/final_model_data/second_island_chain.xlsx") #use this for second island chain
#bases = pd.read_excel("~/Desktop/BlacknRossi2/data/final_model_data/bases.xlsx") #use this for archipelagos in south china sea region
conflict_sites = pd.read_excel("~/Desktop/BlacknRossi2/data/final_model_data/conflict_sites.xlsx")

#compute the transportation cost by calculating distance between suppliers and bases (miles) then multiply by fuel cost per mile
if supplier_base_rela == "Y":
    sup_base_cost = np.zeros(shape=(suppliers.shape[0],bases.shape[0]))
    for i in range(0,suppliers.shape[0]):
        for k in range(0,bases.shape[0]):
            sup_coord = (suppliers.iat[i,suppliers.columns.get_loc("Latitude")],
                         suppliers.iat[i,suppliers.columns.get_loc("Longitude")])
            base_coord = (bases.iat[k, bases.columns.get_loc("Latitude")],
                         bases.iat[k, bases.columns.get_loc("Longitude")])
            sup_base_cost[i,k] = cf.dist_2Coordinates(sup_coord,base_coord)*fuel_cost_per_mile
else:
    #if all supplies come from us (not suppliers in neighboring countries) then put a zero matrix instead
    sup_base_cost = np.zeros(shape=(suppliers.shape[0], bases.shape[0]))

#get number of supplier, center, customer
supplier_num = suppliers.shape[0]
bases_num = bases.shape[0]
conflict_site_num = conflict_sites.shape[0]

#get coordinates from base file
bases_coords = []
for i in range(0,bases_num):
    bases_coords.append((bases.loc[i].at["Latitude"],bases.loc[i].at["Longitude"]))

#get coordinates from conflict site file
conflict_site_coord = []
for i in range(0,conflict_site_num):
    conflict_site_coord.append((conflict_sites.loc[i].at["Latitude"],conflict_sites.loc[i].at["Longitude"]))

#creating distance matrix for base to conflict site, current distance in miles according to function in core function file
#count the number of bases in which supplies can be transported to the site within the interested day_to_site limit, if none, print warning
base_conflict_cost = np.empty(shape=(bases_num,conflict_site_num))
for k in range(0,conflict_site_num):
    count = 0
    for i in range(0,bases_num):
        base_conflict_cost[i,k] = cf.dist_2Coordinates(bases_coords[i],conflict_site_coord[k])
        if (base_conflict_cost[i,k]/(24*ship_speed)) < day_to_site:
            count = count +1
    if count == 0:
        print(f"Warning: There is no base from which supplies can be transported to {conflict_sites.loc[k].at['Name']}")

#get set up and yearly maintainence cost
if base_setup_cost == "Y":
    setup_cost = bases["Set-up"]
    rent = bases["Yearly-rent"] #if there is other annual cost, simply replace the data, dont change the column name in the excel file
    total = setup_cost + year_num*rent
else:
    #if base_setup_cost was N then simply put a 0 array in for total cost
    total = np.zeros(shape=bases_num)

'''Optimization part'''

try:
    #create a model
    model = gp.Model('strategy')

    # add variables (quantity number from supplier to base and from base to conflict site
    sup_base = model.addMVar(shape=(supplier_num,bases_num), vtype=GRB.INTEGER, name="sup_base") #decision var deciding how many supplies from a supplier to a base
    sup_base_shipment = model.addMVar(shape=(supplier_num,bases_num), vtype=GRB.INTEGER, name="sup_base_shipment") #decision variable deciding how many shipments from a supplier to a base
    base_site = model.addMVar(shape=(bases_num,conflict_site_num), vtype=GRB.INTEGER, name="base_site") #decision varible deciding how many supplies from a base to a conflict site
    base_site_shipment = model.addMVar(shape=(bases_num,conflict_site_num), vtype=GRB.INTEGER, name="base_site_shipment") #decision variable deciding how many shipments from a base to a conflict site
    base = model.addMVar(shape=(bases_num),vtype=GRB.BINARY,name="base") #decision variable deciding which base to be used

    # set objective: total cost = transportation cost supplier -> base
    # + transportation cost base -> conflict site
    # + set-up cost + rent cost over the duration
    #assuming transportation cost from center to customer proportional to distance, no current scaling
    #+ setup_cost @ base + year_num*(rent @ base)
    model.setObjective(sum(sup_base_cost[a,:] @ sup_base_shipment[a,:] for a in range(0,supplier_num))
                       + sum(base_conflict_cost[b,:] @ base_site_shipment[b,:] for b in range(0,bases_num))
                       + sum(total[c] * base[c] for c in range(0,bases_num)),GRB.MINIMIZE)

    #number of shipments should be sufficient to deliver the determined amount of supplies shipped from supplier to base
    for i in range(0,supplier_num):
        for k in range(0,bases_num):
            model.addConstr(sup_base[i,k]/ship_capacity <= sup_base_shipment[i,k])

    #number of shipments should be sufficient to deliver the determined amount of supplies shipped from base to conflict site
    for i in range(0,bases_num):
        for k in range(0,conflict_site_num):
            model.addConstr(base_site[i,k]/ship_capacity <= base_site_shipment[i,k])

    #total transport quantity from a supplier to all centers < its total capacity (12)
    #if there is no restriction, put in a number greater than total_supply in column Capacity in supplier file
    for i in range(0,supplier_num):
        temp = sup_base[i,:] @ np.ones(shape=bases_num)
        model.addConstr(temp <= suppliers.loc[i].at["Capacity"])

    #supply from all supplier to a center < max capacity * DV center (13)
    # this assumes that there is a capacity associated with each base, if not, simply replace the capacity column with a huge number (more than total supplies to be stored)
    if base_cap == "Y":
        for i in range(0,bases_num):
            temp = sup_base[:,i] @ np.ones(shape=supplier_num)
            cap = bases.loc[i].at["Capacity"]*base[i]
            model.addConstr(temp <= cap)
    else:
        #in case we want only at most alpha% of all supplies go to each base
        for i in range(0,bases_num):
            temp = sup_base[:,i] @ np.ones(shape=supplier_num)
            cap = total_supply*alpha*base[i]
            model.addConstr(temp <= cap)

    #supply to all confict site from a center < max capacity * DV center (13)
    if base_cap == "Y":
        for i in range(0,bases_num):
            temp = base_site[i,:] @ np.ones(shape=conflict_site_num)
            model.addConstr(temp <= bases.loc[i].at["Capacity"]*base[i])
    else:
        for i in range(0,bases_num):
            temp = base_site[i,:] @ np.ones(shape=conflict_site_num)
            model.addConstr(temp <= total_supply*alpha*base[i])

    #total number of center does not exceed threshold (14)
    temp = base[:] @ np.ones(shape=bases_num)
    model.addConstr(base @ np.ones(shape=bases_num) <= max_center)

    #total transport from a center cannot exceed its supply
    for i in range(0, bases_num):
        input = sup_base[:,i] @ np.ones(shape=supplier_num)
        output = base_site[i,:] @ np.ones(shape=conflict_site_num)
        model.addConstr(output <= input)

    #transport quantity to a site > its demand (16)
    #current data assumes that total supplies will be distributed across all conflict sites in which zones with prev conflicts require 3 times more supplies (more weight)
    for i in range(0,conflict_site_num):
        temp = base_site[:,i] @ np.ones(shape=bases_num)
        model.addConstr(temp >= conflict_sites.loc[i].at["Demand"])

    #no transport to or from center if it is not chosen (17)
    for i in range(0,bases_num):
        temp = sup_base[:,i] @ np.ones(shape=supplier_num)
        model.addConstr(temp <= base[i]*total_supply*2) #total_supply*2 is just big number which provides upper bounnd
        temp = base_site[i,:] @ np.ones(shape=conflict_site_num)
        model.addConstr(temp <= base[i]*total_supply*2) #total_supply*2 is just big number which provides upper bound

    #supplies must be transported from base to conflict site within day_to_site limit
    for i in range(0,bases_num):
        for k in range(0,conflict_site_num):
            model.addConstr(base_site[i,k]/ship_capacity <= base_site_shipment[i,k])

    model.optimize()
    sol_sup_base = sup_base.X
    sol_sup_base_shipment = sup_base_shipment.X
    sol_base_site = base_site.X
    sol_base = base.X
    sol_base_site_shipment = base_site_shipment.X
    objective = model.getObjective().getValue()

    #Iterate over the bases to grab the name
    print(sol_base)
    for i in range(0,bases_num):
        if sol_base[i] >0.5:
            temp_name = bases.loc[i].at["Name"]
            print(f"Chosen center: {temp_name}")

    for i in range(0,supplier_num):
        for k in range(0,bases_num):
            if sol_sup_base[i,k] != 0:
                temp_num = sol_sup_base[i,k]
                temp_sup = suppliers.loc[i].at["Name"]
                temp_base = bases.loc[k].at["Name"]
                print(f"sup - base Transport {temp_num} from {temp_sup} to {temp_base}")
                print(f"sup - base Need {sol_sup_base_shipment[i,k]} shipments from {temp_sup} to {temp_base}")

    for i in range(0,bases_num):
        for k in range(0,conflict_site_num):
            if sol_base_site[i,k] != 0:
                temp_num = sol_base_site[i,k]
                temp_base = bases.loc[i].at["Name"]
                temp_site = conflict_sites.loc[k].at["Name"]
                print(f"base - site Transport {temp_num} from {temp_base} to {temp_site}")
                print(f"base - site Need to use {sol_base_site_shipment[i,k]} from {temp_base} to {temp_site}")

    print(f"The total amount of cost is {objective}. Within the cost, {sum(sup_base_cost[a,:] @ sol_sup_base_shipment[a,:] for a in range(0,supplier_num))} "
          f"is the cost for transportation from suppliers to base. {sum(base_conflict_cost[b,:] @ sol_base_site_shipment[b,:] for b in range(0,bases_num))} "
          f"is the cost for transportation from base to conflict site. {sum(total[c] * sol_base[c] for c in range(0,bases_num))} "
          f"is the cost for maintainence of the chosen base")

except gp.GurobiError as e:
    print('Error code ' + str(e.errno) + ": " + str(e))

except AttributeError:
    print('Encountered an attribute error')

#9682812.48 lbs current