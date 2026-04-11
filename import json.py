import json
import csv
import os
import re

# --- Configuração para Moscou ---
# !! IMPORTANTE !!
# Altere o caminho abaixo para apontar para o arquivo de Moscou.
# Após instalar o pacote (npm install metrostations), o caminho será algo como:
# './node_modules/metrostations/cities/Moscow/stations.json'
CAMINHO_ARQUIVO_JSON = r'node_modules/metrostations/Moscow/Stations/index.json'
NOME_ARQUIVO_CSV = 'metro_moscou.csv'

# --- Função simples para "traduzir" nomes cirílicos para uma forma legível (transliteração) ---
def transliterate_russian_to_latin(text):
    """
    Converte caracteres cirílicos russos em equivalentes latinos simples.
    Isso torna os nomes legíveis em português sem depender de APIs externas.
    """
    if not text:
        return text
    
    # Tabela de transliteração básica (sistema ISO 9 adaptado para legibilidade)
    cyrillic_to_latin = {
        'А': 'A', 'а': 'a', 'Б': 'B', 'б': 'b', 'В': 'V', 'в': 'v',
        'Г': 'G', 'г': 'g', 'Д': 'D', 'д': 'd', 'Е': 'E', 'е': 'e',
        'Ё': 'Yo', 'ё': 'yo', 'Ж': 'Zh', 'ж': 'zh', 'З': 'Z', 'з': 'z',
        'И': 'I', 'и': 'i', 'Й': 'Y', 'й': 'y', 'К': 'K', 'к': 'k',
        'Л': 'L', 'л': 'l', 'М': 'M', 'м': 'm', 'Н': 'N', 'н': 'n',
        'О': 'O', 'о': 'o', 'П': 'P', 'п': 'p', 'Р': 'R', 'р': 'r',
        'С': 'S', 'с': 's', 'Т': 'T', 'т': 't', 'У': 'U', 'у': 'u',
        'Ф': 'F', 'ф': 'f', 'Х': 'Kh', 'х': 'kh', 'Ц': 'Ts', 'ц': 'ts',
        'Ч': 'Ch', 'ч': 'ch', 'Ш': 'Sh', 'ш': 'sh', 'Щ': 'Shch', 'щ': 'shch',
        'Ъ': '', 'ъ': '', 'Ы': 'Y', 'ы': 'y', 'Ь': '', 'ь': '',
        'Э': 'E', 'э': 'e', 'Ю': 'Yu', 'ю': 'yu', 'Я': 'Ya', 'я': 'ya'
    }
    
    result = []
    for char in text:
        result.append(cyrillic_to_latin.get(char, char))
    return ''.join(result)

def carregar_dados(caminho_json):
    """Carrega os dados do arquivo JSON."""
    if not os.path.exists(caminho_json):
        print(f"❌ Erro: Arquivo não encontrado em '{caminho_json}'")
        print("   Verifique se você instalou o pacote 'metrostations' com: npm install metrostations")
        print("   O caminho típico é: ./node_modules/metrostations/cities/Moscow/stations.json")
        return None
    try:
        with open(caminho_json, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            # O arquivo pode ter a chave 'stations' que contém a lista
            if isinstance(dados, dict) and 'stations' in dados:
                return dados['stations']
            return dados
    except json.JSONDecodeError:
        print(f"❌ Erro: O arquivo em '{caminho_json}' não é um JSON válido.")
        return None
    except Exception as e:
        print(f"❌ Erro inesperado ao ler o arquivo: {e}")
        return None

def gerar_csv(estacoes, nome_arquivo):
    """Gera o arquivo CSV a partir da lista de estações."""
    with open(nome_arquivo, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Cabeçalho
        writer.writerow(['id', 'nome_original', 'nome_pt', 'linha', 'conexoes'])

        for estacao in estacoes:
            id_estacao = estacao.get('id')
            
            # O nome 'intl_name' geralmente está em inglês, 'local_name' em russo.
            # Para Moscou, usamos o nome local (russo) e transliteramos para uma forma legível.
            nome_local = estacao.get('local_name') or estacao.get('intl_name') or f"Estação {id_estacao}"
            nome_pt = transliterate_russian_to_latin(nome_local)
            
            linha = estacao.get('line')
            conexoes = estacao.get('stationTransfers', [])
            writer.writerow([id_estacao, nome_local, nome_pt, linha, ','.join(map(str, conexoes))])

    print(f"✅ Arquivo CSV '{nome_arquivo}' gerado com sucesso!")
    print(f"   Total de estações processadas: {len(estacoes)}")

if __name__ == "__main__":
    estacoes = carregar_dados(CAMINHO_ARQUIVO_JSON)
    if estacoes:
        gerar_csv(estacoes, NOME_ARQUIVO_CSV)