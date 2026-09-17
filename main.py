"""
Grid Trading Bot v1.0
This bot activate principal grid trading functionality for specific assets.

The program must not start at higher zone or dead_zone.

bnbwallet:0x13d598485848388110ec4ec3055e7c9731f5efba

###*               $$This Program was written by İlhan Koçaslan$$               *###
"""
#Modules
import time
from binance.client import Client
import json,os

#Connection
privatekey = ""
secretkey = ""
client = Client(privatekey, secretkey)

#Parameters
Asset="MATICUSDT"
Price_Low=1.42
Price_High=1.70
Grid_Number=4
Total_Profit=0
Balance=60
Total_trade=0
flag1=False
#Secondly Parameters
Grid_Area=Grid_Number + 1
Sector_Balance=Balance / Grid_Area
Grid_balance=Price_High - Price_Low
Grid_balance=Grid_balance / Grid_Area


all_sector=[]
#Thirdly Parameters
for lo in range(1,Grid_Area+1):
    name="sector"
    lst=str(lo)
    plus=name + lst

    if lo == 1:
        dead_zone=[0,Price_Low,"$"]
        Higher_zone=[Price_High,9999999,"$"]#hicbir asset in fiyatının 9 milyondan büyük olmayacağı varsayıldı.
        d={}
        d["dead_zone"]=dead_zone
        all_sector.append(d)
        k={}
        k["higher_zone"]=Higher_zone
        all_sector.append(k)
        Lgrid=Price_Low
        Hgrid=Lgrid+Grid_balance
    else:
        Lgrid = Grid_balance*(lo-1) + Price_Low
        Hgrid = Lgrid + Grid_balance


    rammem={}
    rammemgrd=[]
    rammemgrd.append(Lgrid)
    rammemgrd.append(Hgrid)
    rammemgrd.append("$")
    rammemgrd.append(Sector_Balance)
    rammem[plus]=rammemgrd
    rammemgrd=[]

    all_sector.append(rammem)

print(all_sector)
print(Grid_balance)
print(Sector_Balance)

Sector_Balance=f"{Sector_Balance:.2f}"
Sector_Balance=float(Sector_Balance)
print(Sector_Balance,"Sector_balancepre")



def take_currentprice_main(tpair1):
    try:
        al = client.get_symbol_ticker(symbol=tpair1)
    except TimeoutError:
        time.sleep(0.2)
        return "err"
    except:
        return "err1"
    else:
        return al["price"]


def take_currentprice(tpair):
    while (True):
        alprc = take_currentprice_main(tpair)
        if alprc != "err" and alprc != "err1":
            return alprc
        time.sleep(0.4)


def takesymbolinfo_main(bpairs):
    try:
        al = client.get_symbol_info(bpairs)
    except TimeoutError:
        time.sleep(0.2)
        return "err"
    except:
        return "err1"
    else:
        return al


def take_symbolinfo(bpairsx):
    while (True):
        alprc = takesymbolinfo_main(bpairsx)
        if alprc != "err" and alprc != "err1":
            return alprc
        time.sleep(0.4)

def takebalance_mainx(asset1):
    try:
        al = client.get_asset_balance(asset=asset1)
    except TimeoutError:
        time.sleep(0.2)
        return "err"
    except:
        return "err1"
    else:
        return al["free"]


def take_balancex(asset):
    while (True):
        alprc = takebalance_mainx(asset[:-4])
        if alprc != "err" and alprc != "err1":
            return alprc
        time.sleep(0.4)


def take_smarketsell_main(bpairmms, quantmms):
    try:
        order = client.order_market_sell(symbol=bpairmms, quantity=quantmms)
        print(order)
    except TimeoutError:
        print("timeout")
        return "err"
    except Exception as ert:
        print(ert)
        return "err1"
    else:
        return order


def take_smarketsell(bpairms, quantms, steep):
    info = take_symbolinfo(bpairms)
    f = [i["stepSize"] for i in info["filters"] if i["filterType"] == "LOT_SIZE"][0]
    eligible_quant = quantms
    while (True):
        alprc = take_smarketsell_main(bpairms, eligible_quant)
        if alprc != "err" and alprc != "err1":
            return alprc
        eligible_quant -= steep
        eligible_quant = round(eligible_quant, f.index("1") - 1)


def take_smarketbuyy_main(tpairmmb, tbalancemmb):
    try:
        order = client.order_market_buy(symbol=tpairmmb, quoteOrderQty=tbalancemmb)
    except TimeoutError:
        print("timeout")
        return "err"
    except Exception as errm:
        print(errm)
        return "err1"
    else:
        return order


def take_smarketbuyy(tpairmb, tbalancemb):
    while (True):
        alprc = take_smarketbuyy_main(tpairmb, tbalancemb)
        if alprc != "err" and alprc != "err1":
            return alprc
        time.sleep(0.01)


def buy_pair(bpair, binitial_balance):
    order = take_smarketbuyy(bpair, binitial_balance)
    entry_price = order["fills"][0]["price"]
    amount = order["executedQty"]
    amount = float(amount)
    entry_price = float(entry_price)
    listebuy = [amount, entry_price]
    return listebuy


def sell_pair(asset,quan):
    bpair = asset
    amount = quan
    amount = float(amount)
    info = take_symbolinfo(bpair)
    stepp = info['filters'][2]['stepSize']
    stepp = float(stepp)
    f = [i["stepSize"] for i in info["filters"] if i["filterType"] == "LOT_SIZE"][0]
    print(amount, "amount")
    qty = round(amount, f.index("1") - 1)
    print(qty, "amount rounded")
    while (qty > amount):
        qty -= stepp
        print(qty, amount)

    qty -= stepp
    print(bpair, qty, amount, stepp)
    order = take_smarketsell(bpair, qty, stepp)
    result=[]
    result.append(order)
    result.append(True)
    return result

def section_finder():
    global Asset,all_sector
    price=take_currentprice(Asset)
    price=float(price)
    for sfo in all_sector:
        for sfoo in sfo.keys():
            sfooval = sfo[sfoo]
            mingrid = sfooval[0]
            maxgrid = sfooval[1]
            mingrid = float(mingrid)
            maxgrid = float(maxgrid)
            if mingrid <= price < maxgrid:
                return sfoo


def asordol_finder(sectorda):
    global all_sector
    for aso in all_sector:
        for asoo in aso.keys():
            asooval=aso[asoo]
            asor=asooval[2]
            asor=str(asor)
            return asor

def update_asordolsector(sectorx,direction):
    global all_sector
    if direction == "$":
        for aso in all_sector:
            for asoo in aso.keys():
                if asoo == sectorx:
                    asooval = aso[asoo]
                    asooval[2]="$"
    else:
        for aso in all_sector:
            for asoo in aso.keys():
                if asoo == sectorx:
                    asooval = aso[asoo]
                    asooval[2]="A"


def update_asordolsectorda(sectorx,direction,quant):
    global all_sector
    if direction == "$":
        for aso in all_sector:
            for asoo in aso.keys():
                if asoo == sectorx:
                    asooval = aso[asoo]
                    asooval[3]=quant
    else:
        for aso in all_sector:
            for asoo in aso.keys():
                if asoo == sectorx:
                    asooval = aso[asoo]
                    asooval[3]=quant

def take_aserdol(sectorxi):
    global all_sector
    for aso in all_sector:
        for asoo in aso.keys():
            if asoo == sectorxi:
                asooval = aso[asoo]
                astake = asooval[3]
                return astake


def informer():
    global Total_trade,Total_Profit

    path = os.getcwd()
    path += "/" + "loggrid.json"
    lastdict = {}
    with open(path, "r") as rdx:
        lastdict = json.load(rdx)

    lastdict[Total_trade] = Total_Profit
    with open(path, "w") as trx:
        json.dump(lastdict, trx)











while(True):

    if Total_trade % 10 == 0:
        informer()
    Total_Profit=Total_trade*Sector_Balance
    lst=section_finder()
    print(lst,"last")
    while(True):
        new=section_finder()
        time.sleep(0.1)
        print(new,"new")
        if lst != new:
            print("eşitlik Bozuldu")
            if new == "higher_zone":
                print("hzone bölgesinde")
                asorhigher=asordol_finder(lst)
                if asorhigher == "$":
                    while(True):
                        time.sleep(1)
                        hzfind=section_finder()
                        if hzfind == "higher_zone":
                            print("higher zone")
                        else:
                            break
                    break
                else:
                    takeassetquan = take_aserdol(lst)
                    sell_pair(Asset,takeassetquan)
                    update_asordolsector(lst, "$")
                    update_asordolsectorda(lst, "$", Sector_Balance)
                    Total_trade+=1
                    while(True):
                        time.sleep(1)
                        hzfindd=section_finder()
                        if hzfindd == "higher_zone":
                            print("higher_zone")
                        else:
                            break
                    break
            else:
                if new == "dead_zone":
                    asordead=asordol_finder(lst)
                    if asordead == "$":
                        as1 = buy_pair(Asset, Sector_Balance)
                        update_asordolsector(lst, "A")
                        update_asordolsectorda(lst, "A", as1[0])
                        while(True):
                            time.sleep(1)
                            dnew=section_finder()
                            if dnew == "dead_zone":
                                print("dead_zone")
                            else:
                                break
                        break
                    else:
                        while(True):
                            time.sleep(1)
                            ddnew = section_finder()
                            if ddnew == "dead_zone":
                                print("dead_zone")
                            else:
                                break
                        break
                else:
                    new_numeric=new[6:]
                    lst_numeric=lst[6:]
                    new_numeric=int(new_numeric)
                    lst_numeric=int(lst_numeric)
                    if new_numeric > lst_numeric:
                        asorup=asordol_finder(lst)
                        if asorup == "$":
                            break
                        else:
                            takeassetquan=take_aserdol(lst)
                            sell_pair(Asset,takeassetquan)
                            update_asordolsector(lst,"$")
                            update_asordolsectorda(lst, "$",Sector_Balance)
                            Total_trade+=1
                    else:
                        asordollar=asordol_finder(lst)
                        if asordollar == "$":
                            as1=buy_pair(Asset,Sector_Balance)
                            update_asordolsector(lst,"A")
                            update_asordolsectorda(lst,"A",as1[0])
                            break
                        else:
                            break
"""

"""
