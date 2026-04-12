import csv
import webbrowser
from collections import defaultdict, deque
import folium

# ------------------------------------------------------------
# CONFIGURACOES
# ------------------------------------------------------------
ARQUIVO_ARESTAS = "arestas_completas.csv"
ARQUIVO_ESTACOES = "metro_moscou.csv"


# ------------------------------------------------------------
# CARREGAMENTO DO GRAFO
# ------------------------------------------------------------
def carregar_grafo(arquivo_arestas, arquivo_estacoes):
    grafo = defaultdict(list)
    info = {}                # id -> (nome_pt, nome_original, nome_trans, linha)
    nome_para_ids = defaultdict(list)
    coords = {}              # id -> (lat, lon)
    linha_estacao = {}       # id -> nome da linha

    # Carregar ordem das estacoes por linha (para desenho continuo)
    linhas_estacoes = defaultdict(list)
    with open(arquivo_estacoes, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            id_simples = row[0]
            linha = row[3]
            linhas_estacoes[linha].append(id_simples)

    with open(arquivo_arestas, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            u = str(row["origem_id"])
            v = str(row["destino_id"])
            tempo = int(row["tempo_seg"])

            grafo[u].append((v, tempo))
            grafo[v].append((u, tempo))

            lat_u = float(row["lat_origem"]) if row["lat_origem"] else None
            lon_u = float(row["lon_origem"]) if row["lon_origem"] else None
            lat_v = float(row["lat_destino"]) if row["lat_destino"] else None
            lon_v = float(row["lon_destino"]) if row["lon_destino"] else None
            if lat_u and lon_u:
                coords[u] = (lat_u, lon_u)
            if lat_v and lon_v:
                coords[v] = (lat_v, lon_v)

            linha = row["linha_origem"]
            linha_estacao[u] = linha
            linha_estacao[v] = linha

            for est_id, nome_pt, nome_orig, nome_trans in [
                (u, row["nome_pt_origem"], row["nome_original_origem"], row["nome_trans_origem"]),
                (v, row["nome_pt_destino"], row["nome_original_destino"], row["nome_trans_destino"]),
            ]:
                if est_id not in info:
                    info[est_id] = (nome_pt, nome_orig, nome_trans, linha)
                    for termo in [nome_pt, nome_orig, nome_trans]:
                        termo_lower = termo.lower()
                        if est_id not in nome_para_ids[termo_lower]:
                            nome_para_ids[termo_lower].append(est_id)

    return grafo, info, nome_para_ids, coords, linha_estacao, linhas_estacoes


# ------------------------------------------------------------
# BFS (MENOR NUMERO DE TRECHOS/ESTACOES)
# ------------------------------------------------------------
def bfs_menor_estacoes(grafo, origem, destino):
    fila = deque([origem])
    visitados = {origem}
    prev = {}

    while fila:
        u = fila.popleft()
        if u == destino:
            break

        for v, _ in grafo.get(u, []):
            if v not in visitados:
                visitados.add(v)
                prev[v] = u
                fila.append(v)

    if destino not in visitados:
        return None

    caminho = []
    cur = destino
    while cur != origem:
        caminho.append(cur)
        cur = prev[cur]
    caminho.append(origem)
    caminho.reverse()
    return caminho


def calcular_tempo_caminho(grafo, caminho):
    """Soma os tempos das arestas para exibir o tempo total do caminho BFS."""
    if not caminho or len(caminho) < 2:
        return 0

    total = 0
    for i in range(len(caminho) - 1):
        u, v = caminho[i], caminho[i + 1]
        peso = None
        for viz, tempo in grafo.get(u, []):
            if viz == v:
                peso = tempo
                break
        if peso is None:
            return None
        total += peso
    return total


# ------------------------------------------------------------
# BUSCA DE ESTACOES
# ------------------------------------------------------------
def buscar_estacao(termo, nome_para_ids, info):
    termo = termo.lower()
    resultados = []
    vistos = set()
    for chave, ids in nome_para_ids.items():
        if termo in chave:
            for id_est in ids:
                if id_est not in vistos:
                    vistos.add(id_est)
                    nome_pt, nome_orig, nome_trans, linha = info.get(
                        id_est, (id_est, id_est, id_est, "?")
                    )
                    resultados.append((id_est, nome_pt, linha))
    return resultados


# ------------------------------------------------------------
# GERACAO DE MAPA COM FOLIUM
# ------------------------------------------------------------
def gerar_mapa(grafo, coords, linha_estacao, info, linhas_estacoes, caminho=None):
    # Paleta de cores para as linhas
    cores_linhas = {}
    paleta = [
        "#e6194B", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
        "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff",
        "#9A6324", "#fffac8", "#800000", "#aaffc3", "#808000", "#ffd8b1",
    ]
    for i, linha in enumerate(set(linha_estacao.values())):
        cores_linhas[linha] = paleta[i % len(paleta)]

    # Mapa base CartoDB Voyager (limpo)
    mapa = folium.Map(
        location=[55.7558, 37.6173],
        zoom_start=11,
        tiles="CartoDB voyager",
        attr="CartoDB",
    )

    # --- Desenha conexoes continuas por linha (ignorando estacoes sem coordenadas) ---
    for linha, ids in linhas_estacoes.items():
        cor = cores_linhas.get(linha, "gray")
        ultima_com_coord = None
        for est_id in ids:
            if est_id in coords:
                if ultima_com_coord is not None:
                    folium.PolyLine(
                        locations=[coords[ultima_com_coord], coords[est_id]],
                        color=cor,
                        weight=4.5,
                        opacity=0.85,
                    ).add_to(mapa)
                ultima_com_coord = est_id

    # --- Desenha tambem arestas de baldeacao (entre linhas diferentes) ---
    arestas_desenhadas = set()
    for u, vizinhos in grafo.items():
        if u not in coords:
            continue
        for v, _ in vizinhos:
            if v not in coords:
                continue
            aresta = tuple(sorted((u, v)))
            if aresta in arestas_desenhadas:
                continue
            arestas_desenhadas.add(aresta)
            linha = linha_estacao.get(u, "Desconhecida")
            cor = cores_linhas.get(linha, "gray")
            folium.PolyLine(
                locations=[coords[u], coords[v]],
                color=cor,
                weight=4.5,
                opacity=0.85,
            ).add_to(mapa)

    # --- Marcadores das estacoes ---
    for est_id, (lat, lon) in coords.items():
        nome_pt, _, _, _ = info.get(est_id, (est_id, "", "", ""))
        folium.CircleMarker(
            location=(lat, lon),
            radius=5,
            color="#333333",
            fill=True,
            fill_color="white",
            fill_opacity=1.0,
            weight=1.5,
            popup=folium.Popup(nome_pt, max_width=200),
        ).add_to(mapa)

    # --- Destaca a rota ---
    if caminho:
        for i in range(len(caminho) - 1):
            u, v = caminho[i], caminho[i + 1]
            if u in coords and v in coords:
                folium.PolyLine(
                    locations=[coords[u], coords[v]],
                    color="#FFD700",
                    weight=8,
                    opacity=1.0,
                ).add_to(mapa)

        if caminho[0] in coords:
            folium.Marker(
                location=coords[caminho[0]],
                popup=f"<b>INICIO:</b><br>{info[caminho[0]][0]}",
                icon=folium.Icon(color="green", icon="play", prefix="fa"),
            ).add_to(mapa)
        if caminho[-1] in coords:
            folium.Marker(
                location=coords[caminho[-1]],
                popup=f"<b>DESTINO:</b><br>{info[caminho[-1]][0]}",
                icon=folium.Icon(color="red", icon="stop", prefix="fa"),
            ).add_to(mapa)

    # --- Legenda ---
    legend_html = """
    <div style="position: fixed; bottom: 20px; left: 20px; width: 200px;
                background: white; border:2px solid grey; z-index:9999;
                font-size:12px; padding: 10px; border-radius: 6px;
                max-height: 300px; overflow-y: auto;">
    <b>Linhas do Metro</b><br>
    """
    for linha, cor in cores_linhas.items():
        legend_html += f'<span style="color:{cor};">⬤</span> {linha}<br>'
    legend_html += "</div>"
    mapa.get_root().html.add_child(folium.Element(legend_html))

    mapa.save("rota_metro_bfs.html")
    webbrowser.open("rota_metro_bfs.html")


# ------------------------------------------------------------
# INTERFACE PRINCIPAL
# ------------------------------------------------------------
def main():
    print("Carregando dados do metro de Moscou (BFS)...")
    try:
        grafo, info, nome_para_ids, coords, linha_estacao, linhas_estacoes = carregar_grafo(
            ARQUIVO_ARESTAS, ARQUIVO_ESTACOES
        )
    except FileNotFoundError as e:
        print(f"Arquivo nao encontrado: {e}")
        print("   Certifique-se de que 'arestas_completas.csv' e 'metro_moscou.csv' estao na pasta.")
        return

    print(f"{len(grafo)} estacoes carregadas.\n")

    while True:
        print("\n" + "-" * 40)
        termo = input("Estacao de origem (parte do nome ou 'sair'): ").strip()
        if termo.lower() == "sair":
            break
        res_orig = buscar_estacao(termo, nome_para_ids, info)
        if not res_orig:
            print("Nenhuma estacao encontrada.")
            continue
        print("\nEstacoes encontradas:")
        for i, (id_est, nome, linha) in enumerate(res_orig[:10], 1):
            print(f"   {i}. {nome} (Linha {linha})")
        try:
            escolha = int(input("Numero: ")) - 1
        except ValueError:
            print("Entrada invalida.")
            continue
        if escolha < 0 or escolha >= len(res_orig):
            print("Numero invalido.")
            continue
        id_origem = res_orig[escolha][0]

        termo = input("\n Estacao de destino: ").strip()
        res_dest = buscar_estacao(termo, nome_para_ids, info)
        if not res_dest:
            print("Nenhuma estacao encontrada.")
            continue
        print("\n Estacoes encontradas:")
        for i, (id_est, nome, linha) in enumerate(res_dest[:10], 1):
            print(f"   {i}. {nome} (Linha {linha})")
        try:
            escolha = int(input("Numero: ")) - 1
        except ValueError:
            print("Entrada invalida.")
            continue
        if escolha < 0 or escolha >= len(res_dest):
            print("Numero invalido.")
            continue
        id_destino = res_dest[escolha][0]

        print("\n Calculando rota BFS (menor numero de trechos)...")
        caminho = bfs_menor_estacoes(grafo, id_origem, id_destino)
        if caminho is None:
            print("Rota nao encontrada.")
        else:
            qtd_trechos = len(caminho) - 1
            qtd_estacoes = len(caminho)
            tempo_total = calcular_tempo_caminho(grafo, caminho)

            print(f"Menor numero de trechos: {qtd_trechos}")
            print(f"Quantidade de estacoes no caminho: {qtd_estacoes}")
            if tempo_total is not None:
                print(f"Tempo desse caminho BFS: {tempo_total // 60} min {tempo_total % 60} seg")

            print("Estacoes:")
            for i, est in enumerate(caminho):
                nome, _, _, linha = info[est]
                print(f"   {i+1}. {nome} (Linha {linha})")

            print("\n Gerando mapa...")
            gerar_mapa(grafo, coords, linha_estacao, info, linhas_estacoes, caminho)
            print("   Mapa salvo como 'rota_metro_bfs.html' e aberto no navegador.")

        if input("\nNova consulta? (s/n): ").lower() != "s":
            break

    print("\n Obrigado por usar o planejador BFS do metro de Moscou!")


if __name__ == "__main__":
    main()
