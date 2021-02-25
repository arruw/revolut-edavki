# Slovenian TAX report XML generator for Revolut Trading

Use [bogdanghervan/revolut-statement](https://github.com/bogdanghervan/revolut-statement) to convert monthly statements into the `<revolut_activity_csv>`.

https://github.com/jamsix/ib-edavki

```bash
$ python generate-xml.py --input <revolut_activity_csv> --id <tax_number> --name <name> --surname <last_name> --year <year>
```