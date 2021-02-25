import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
from pprint import pprint
import requests
from lxml import etree
import click
import decimal as D

import os, sys

FOURPLACES = D.Decimal(10) ** -4

def toDate(string):
  return datetime.strptime(string, "%m/%d/%Y").date()

def dateFormat(date):
  return date.strftime("%Y-%m-%d")

def getRate(date):
  if not os.path.exists(".cache/rates.xml"):
    req = requests.get("https://www.bsi.si/_data/tecajnice/dtecbs-l.xml", allow_redirects=True)
    os.mkdir(".cache")
    with open(".cache/rates.xml", "wb") as f: f.write(req.content)

  xml = etree.parse(".cache/rates.xml")
  rate = xml.xpath("//x:tecajnica[@datum=$date]/x:tecaj[@oznaka='USD']/text()", namespaces={"x": "http://www.bsi.si"}, date=date)

  return None if len(rate) == 0 else 1/D.Decimal(rate[0])

def toDecimal(x):
  try:
    return D.Decimal(x)
  except:
    return None

@click.command()
@click.option("--input",      required=True, help="Revolut Activity CSV file")
@click.option("--id",         required=True, help="TAX number")
@click.option("--fullname",   required=True, help="Full Name")
@click.option("--address",    required=True, help="Last Name")
@click.option("--zip",        required=True, help="ZIP")
@click.option("--city",       required=True, help="City")
@click.option("--dob",        required=True, help="Date of birth YYYY-MM-DD")
@click.option("--tel",        required=True, help="Telephone")
@click.option("--email",      required=True, help="Email")
def main(input, id, fullname, address, zip, city, dob, tel, email):
  isindb = pd.read_csv("db/isin.csv")

  activity = pd.read_csv(input, 
    converters={"Quantity": toDecimal, "Price": toDecimal, "Amount": toDecimal}
    )
  activity["Trade Date"] = activity["Trade Date"].map(toDate)
  activity["Settle Date"] = activity["Settle Date"].map(toDate)
  del activity['Description']
  del activity['Symbol / Description']
  activity = activity[(activity['Activity Type'] == 'BUY') | (activity['Activity Type'] == 'SELL') | (activity['Activity Type'] == 'SSP')]

  root_el = ET.Element("Envelope", attrib={
    "xmlns": "http://edavki.durs.si/Documents/Schemas/Doh_KDVP_9.xsd",
    "xmlns:edp": "http://edavki.durs.si/Documents/Schemas/EDP-Common-1.xsd",
    "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "xsi:schemaLocation": "http://www.w3.org/2001/XMLSchema-instance http://www.w3.org/2001/XMLSchema-instance http://edavki.durs.si/Documents/Schemas/Doh_KDVP_9.xsd https://edavki.durs.si/Documents/Schemas/Doh_KDVP_9.xsd http://edavki.durs.si/Documents/Schemas/EDP-Common-1.xsd http://edavki.durs.si/Documents/Schemas/EDP-Common-1.xsd"
  })

  header_el = ET.SubElement(root_el, "edp:Header")
  taxpayer_el = ET.SubElement(header_el, "edp:taxpayer")

  # TODO
  ET.SubElement(taxpayer_el, "edp:taxNumber").text = id
  ET.SubElement(taxpayer_el, "edp:taxpayerType").text = "FO"
  ET.SubElement(taxpayer_el, "edp:name").text = fullname
  ET.SubElement(taxpayer_el, "edp:address1").text = address
  ET.SubElement(taxpayer_el, "edp:city").text = city
  ET.SubElement(taxpayer_el, "edp:postNumber").text = zip
  ET.SubElement(taxpayer_el, "edp:birthDate").text = dob

  ET.SubElement(root_el, "edp:AttachmentList")
  ET.SubElement(root_el, "edp:Signatures")

  body_el = ET.SubElement(root_el, "body")
  ET.SubElement(body_el, "edp:bodyContent")
  dohkdvp_el = ET.SubElement(body_el, "Doh_KDVP")
  kdvp_el = ET.SubElement(dohkdvp_el, "KDVP")

  # TODO
  ET.SubElement(kdvp_el, "DocumentWorkflowID").text = "O" # I or O
  ET.SubElement(kdvp_el, "Year").text = "2020"
  ET.SubElement(kdvp_el, "PeriodStart").text = "2020-01-01"
  ET.SubElement(kdvp_el, "PeriodEnd").text = "2020-12-31"
  ET.SubElement(kdvp_el, "IsResident").text = "true"
  ET.SubElement(kdvp_el, "TelephoneNumber").text = tel
  ET.SubElement(kdvp_el, "SecurityCount").text = str(len(activity['Symbol'].unique()))
  ET.SubElement(kdvp_el, "SecurityShortCount").text = "0"
  ET.SubElement(kdvp_el, "SecurityWithContractCount").text = "0"
  ET.SubElement(kdvp_el, "SecurityWithContractShortCount").text = "0"
  ET.SubElement(kdvp_el, "ShareCount").text = "0"
  ET.SubElement(kdvp_el, "Email").text = email

  row_id = 0

  for symbol in activity['Symbol'].unique():
    symbol_activity = activity[(activity['Symbol'] == symbol)]

    if len(symbol_activity[(symbol_activity["Quantity"] < 0)].index) == 0:
      print(f"[WARN] Skipping {symbol} because there was no sells")
      continue

    kdvpitem_el = ET.SubElement(dohkdvp_el, "KDVPItem")
    ET.SubElement(kdvpitem_el, "InventoryListType").text = "PLVP"
    ET.SubElement(kdvpitem_el, "Name").text = symbol
    ET.SubElement(kdvpitem_el, "HasForeignTax").text = "false"
    ET.SubElement(kdvpitem_el, "HasLossTransfer").text = "true"
    ET.SubElement(kdvpitem_el, "ForeignTransfer").text = "false"
    ET.SubElement(kdvpitem_el, "TaxDecreaseConformance").text = "false"

    securities_el = ET.SubElement(kdvpitem_el, "Securities")
    ET.SubElement(securities_el, "Code").text = symbol
    ET.SubElement(securities_el, "IsFond").text = "false"

    for index, sa in symbol_activity.iterrows():
      date = dateFormat(sa["Settle Date"])
      amount = sa["Quantity"].quantize(FOURPLACES)
      priceUSD = sa["Price"]
      rate = getRate(date)
      priceEUR = (priceUSD * rate).quantize(FOURPLACES)

      row_el = ET.SubElement(securities_el, "Row")
      ET.SubElement(row_el, "ID").text = str(row_id)
      row_id += 1

      if amount >= 0:
        purchase_el = ET.SubElement(row_el, "Purchase")
        ET.SubElement(purchase_el, "F1").text = date
        ET.SubElement(purchase_el, "F2").text = "B" # nakup
        ET.SubElement(purchase_el, "F3").text = str(amount)
        ET.SubElement(purchase_el, "F4").text = str(priceEUR)
      else:
        sale_el = ET.SubElement(row_el, "Sale")
        ET.SubElement(sale_el, "F6").text = date
        ET.SubElement(sale_el, "F7").text = str(abs(amount))
        ET.SubElement(sale_el, "F9").text = str(priceEUR)
        ET.SubElement(sale_el, "F10").text = "true"

  output = input.replace(".csv", ".xml")
  ET.ElementTree(root_el).write(output, encoding='utf8', method='xml')
  etree.parse(output).write(output, pretty_print=True, xml_declaration=True, encoding='UTF-8')


if __name__ == "__main__":
  main()