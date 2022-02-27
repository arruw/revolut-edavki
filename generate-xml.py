import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
from lxml import etree
import click
import decimal as D

import os

FOURPLACES = D.Decimal(10) ** -4

def toDate(string):
  string = string.strip()[:10]
  return datetime.strptime(string, "%d/%m/%Y").date()

def dateFormat(date):
  return date.strftime("%Y-%m-%d")

def getRate(date, currency):
  if not os.path.exists(".cache/rates.xml"):
    req = requests.get("https://www.bsi.si/_data/tecajnice/dtecbs-l.xml", allow_redirects=True)
    os.mkdir(".cache")
    with open(".cache/rates.xml", "wb") as f: f.write(req.content)

  xml = etree.parse(".cache/rates.xml")
  rate = xml.xpath(f"//x:tecajnica[@datum=$date]/x:tecaj[@oznaka='{currency}']/text()", namespaces={"x": "http://www.bsi.si"}, date=date)

  return None if len(rate) == 0 else 1/D.Decimal(rate[0])

def toDecimal(x):
  try:
    return D.Decimal(x)
  except:
    return None

def strippedString(s):
  return s.strip()

@click.command()
@click.option("--input",      required=True, help="Revolut Activity CSV file")
@click.option("--id",         required=True, help="TAX number")
@click.option("--fullname",   required=True, help="Full Name")
@click.option("--address",    required=True, help="Address")
@click.option("--zip",        required=True, help="ZIP")
@click.option("--city",       required=True, help="City")
@click.option("--dob",        required=True, help="Date of birth YYYY-MM-DD")
@click.option("--tel",        required=True, help="Telephone")
@click.option("--email",      required=True, help="Email")
def main():
  main(input, id, fullname, address, zip, city, dob, tel, email)

def main(input, id, fullname, address, zip, city, dob, tel, email):
  isindb = pd.read_csv("db/isin.csv")

  activity = pd.read_csv(
    input, 
    sep = ';',
    converters={"Quantity": toDecimal,
                "Price per share": toDecimal,
                "Total Amount": toDecimal,
                'Date': toDate,
                'Type': strippedString,
                'Currency': strippedString,
              }
  )

  type_mapping = {
    'EIS Investment': 'BUY',
    'EIS Sale': 'SELL',
    'SEIS Investment': 'BUY',
    'SEIS Sale': 'SELL',
    'Investment': 'BUY',
    'Sale': 'SELL',
    'Purchase': 'BUY',
  }
  for key in type_mapping.keys():
    activity['Type'] = activity['Type'].replace([key], type_mapping[key])

  activity = activity[(activity['Type'] == 'BUY') | (activity['Type'] == 'SELL')]

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
  ET.SubElement(kdvp_el, "Year").text = "2021"
  ET.SubElement(kdvp_el, "PeriodStart").text = "2021-01-01"
  ET.SubElement(kdvp_el, "PeriodEnd").text = "2021-12-31"
  ET.SubElement(kdvp_el, "IsResident").text = "true"
  ET.SubElement(kdvp_el, "TelephoneNumber").text = tel
  ET.SubElement(kdvp_el, "SecurityCount").text = str(len(activity['Ticker'].unique()))
  ET.SubElement(kdvp_el, "SecurityShortCount").text = "0"
  ET.SubElement(kdvp_el, "SecurityWithContractCount").text = "0"
  ET.SubElement(kdvp_el, "SecurityWithContractShortCount").text = "0"
  ET.SubElement(kdvp_el, "ShareCount").text = "0"
  ET.SubElement(kdvp_el, "Email").text = email

  ticker_mapping = {
    'VACQ': 'RKLB',
  }
  for key in ticker_mapping.keys():
    activity['Ticker'] = activity['Ticker'].replace([key], ticker_mapping[key])

  row_id = 0
  for symbol in activity['Ticker'].unique():
    symbol_activity = activity[(activity['Ticker'] == symbol )]

    if 0 == len(symbol_activity[symbol_activity["Type"] == 'SELL']) :
      print(f"[WARNING] Skipping {symbol} because there was no sells")
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
      date = dateFormat(sa["Date"])
      qty = sa["Quantity"]
      price = sa["Price per share"]
      total = sa["Total Amount"]
      if abs(qty * price - total) > 1e-1:
        raise Exception("[ERROR] Copied wrong values?")
      qty = qty.quantize(FOURPLACES)

      if sa["Currency"] == 'EUR':
        sharepriceEUR = price
      else:
        rate = getRate(date, sa["Currency"])
        sharepriceEUR = (price * rate).quantize(FOURPLACES)

      row_el = ET.SubElement(securities_el, "Row")
      ET.SubElement(row_el, "ID").text = str(row_id)
      row_id += 1

      type = sa["Type"]
      if type == "BUY":
        purchase_el = ET.SubElement(row_el, "Purchase")
        ET.SubElement(purchase_el, "F1").text = date
        ET.SubElement(purchase_el, "F2").text = "B" # nakup
        ET.SubElement(purchase_el, "F3").text = str(qty)
        ET.SubElement(purchase_el, "F4").text = str(sharepriceEUR)
      elif type == "SELL":
        sale_el = ET.SubElement(row_el, "Sale")
        ET.SubElement(sale_el, "F6").text = date
        ET.SubElement(sale_el, "F7").text = str(qty)
        ET.SubElement(sale_el, "F9").text = str(sharepriceEUR)
        ET.SubElement(sale_el, "F10").text = "true"
      else:
        raise Exception("[ERROR] Filter for Transaction Types not working?")

  output = input.replace(".csv", ".xml")
  ET.ElementTree(root_el).write(output, encoding='utf8', method='xml')
  etree.parse(output).write(output, pretty_print=True, xml_declaration=True, encoding='UTF-8')


if __name__ == "__main__":
  main()