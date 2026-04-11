import csv

with open('arestas_completas.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['origem_id'] in ['150', '151', '152'] or row['destino_id'] in ['150', '151', '152']:
            print(f"{row['origem_id']} -> {row['destino_id']} | lat_origem: {row['lat_origem']}, lon_origem: {row['lon_origem']}, lat_destino: {row['lat_destino']}, lon_destino: {row['lon_destino']}")