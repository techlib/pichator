import xlsxwriter
from io import BytesIO
from pprint import pprint as pp

def xlsx_export(data, dept, month, year, **kwargs):
  output = BytesIO()
  workbook = xlsxwriter.Workbook(output)
  worksheet = workbook.add_worksheet(dept) # nazev listu

  doc_name = 'Docházka za útvar {dept}'.format(dept=dept)
  period = 'Za období: {month} - {year}'.format(month=month, year=year)

  # Add a bold format to use to highlight cells.
  bold = workbook.add_format({'bold': True})

  if len(data) > 0:

    worksheet.write('A1', doc_name, bold)
    worksheet.write('A3', period)


    # nazvy sloupecku
    worksheet.write('A5', 'Číslo zaměstnance', bold)
    worksheet.write('B5', 'Jméno zaměstnance', bold)

    # datum 
    for date in range(1, len(data[0])-1):
      worksheet.write(5, date+2, date, bold)

    row = 6
    col = 3
    for emp in data:
      worksheet.write(row, 0, emp['pvid']) #pracovni pomer
      worksheet.write(row, 1, emp['name']) #jmeno
      for day in range(1, len(data[0])-1):
        worksheet.write(row, col, emp.get(str(day), ''))
        col += 1
      col = 3
      row += 1
  else:
    # nejsou data
    worksheet.write('A5', 'Prázdná odpověď', bold)
    worksheet.write('A6', 'Dotaz vrátil prázdný záznam.')
    worksheet.write('A7', 'Žádný zaměstnanec tohoto útvaru nemá platný PV, nebo vyplněnou pracovní dobu.')
    worksheet.write('A8', 'Pokud si myslíte, že se jedná o chybu, kontaktujte prosím mailto:helpdeskict@techlib.cz')




  workbook.close()
  output.seek(0)
  return output

    # {% if data[0]|length %}
    #   <table>
    #       <thead>
    #           <th></th>
    #           {% for day in range(1, data[0]|length) %}
    #           <th>{{ day }}</th>
    #           {% endfor %}
    #       </thead>
    #       <tbody>
    #           {% for emp in data %}
    #           <tr>
    #               <td>{{ emp['name'] }}</td>
    #               {% for day in range(1, data[0]|length) %}
    #               <td>{{ emp[day|string] }}</td>
    #               {% endfor %}
    #           </tr>
    #           {% endfor %}
    #       </tbody>
    #   </table>
    # {% else %}