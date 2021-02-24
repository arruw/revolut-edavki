import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
from lxml import etree
import click

import os, sys

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

  return None if len(rate) == 0 else float(rate[0])

@click.command()
@click.option("--input",   required=True, help="Revolut Activity CSV file")
@click.option("--id",      required=True, help="TAX number")
@click.option("--name",    required=True, help="First Name")
@click.option("--surname", required=True, help="Last Name")
@click.option("--year",    required=True, help="Year")
def main(input, id, name, surname, year):
  isindb = pd.read_csv("db/isin.csv")

  activity = pd.read_csv(input)
  activity["Trade Date"] = activity["Trade Date"].map(toDate)
  activity["Settle Date"] = activity["Settle Date"].map(toDate)
  del activity['Description']
  del activity['Symbol / Description']
  activity = activity[(activity['Activity Type'] == 'BUY') | (activity['Activity Type'] == 'SELL')]

  root = ET.Element("Data")
  root.attrib["xmlns"] = "http://edavki.durs.si/Documents/Schemas/KP_KDVP_2.xsd"
  root.attrib["xmlns:edp"] = "http://edavki.durs.si/Documents/Schemas/EDP-Common-1.xsd"
  root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
  root.attrib["xsi:schemaLocation"] = "http://www.w3.org/2001/XMLSchema-instance http://www.w3.org/2001/XMLSchema-instance http://edavki.durs.si/Documents/Schemas/KP_KDVP_2.xsd http://edavki.durs.si/Documents/Schemas/KP_KDVP_2.xsd http://edavki.durs.si/Documents/Schemas/EDP-Common-1.xsd http://edavki.durs.si/Documents/Schemas/EDP-Common-1.xsd"

  year_el = ET.SubElement(root, "Year")
  year_el.text = year

  tud_el = ET.SubElement(root, "TransactionUserData",
    Id=id,
    Name=name,
    Surname=surname,
    Resident="R",
    CountryOfResidenceName="SI")

  for symbol in activity['Symbol'].unique():
    symbol_activity = activity[(activity['Symbol'] == symbol)]
    symbol_activity = symbol_activity.sort_values("Settle Date")

    try:
      isin = isindb[(isindb["Symbol"] == symbol)]["ISIN"].item()
    except:
      isin = "ERROR"
      print(f"[ERROR] Missing ISIN for the {symbol}.")

    podvp_el = ET.SubElement(tud_el, "PODVP",
      ISIN=isin,
      Name=symbol)

    for index, sa in symbol_activity.iterrows():
      date = dateFormat(sa["Settle Date"])
      amount = abs(sa["Quantity"])
      priceUSD = float(sa["Price"])
      rate = getRate(date)
      priceEUR = priceUSD * (1/rate)

      el_type = "Purchase" if sa["Activity Type"] == "BUY" else "Sale"
      ET.SubElement(podvp_el, el_type,
        Date=date,
        Amount=f"{amount:.4f}",
        Value=f"{priceEUR:.4f}")

  output = input.replace(".csv", ".xml")
  ET.ElementTree(root).write(output, encoding='utf8', method='xml')
  etree.parse(output).write(output, pretty_print=True, xml_declaration=True, encoding='UTF-8')


if __name__ == "__main__":
  main()