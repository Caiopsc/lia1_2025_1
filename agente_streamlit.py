import streamlit as st
import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
import requests # Nova importação para requisições HTTP
import json     # Nova importação para lidar com JSON

# --- Configuração Inicial ---
load_dotenv()

# Configurações para Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    st.error("Erro: A chave API do Gemini (GEMINI_API_KEY) não foi encontrada no arquivo .env.")
    st.stop()
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash') # Ou 'gemini-1.5-flash'

# Configurações para OpenRouteService
ORS_API_KEY = os.getenv('ORS_API_KEY')
ORS_API_BASE_URL = "https://api.openrouteservice.org/v2/directions/cycling-regular" # Roteamento para ciclismo regular

if not ORS_API_KEY:
    st.warning("Aviso: A chave API do OpenRouteService (ORS_API_KEY) não foi encontrada no arquivo .env. Funções de mapa não estarão disponíveis.")

# --- Função para Obter Rota do OpenRouteService ---
def get_ors_route(start_coords, end_coords, api_key):
    if not api_key:
        return None, "Chave API do OpenRouteService não configurada."

    headers = {
        'Accept': 'application/json',
        'Authorization': api_key
    }
    body = {
        "coordinates": [
            [start_coords[1], start_coords[0]], # ORS espera [longitude, latitude]
            [end_coords[1], end_coords[0]]
        ]
    }
    
    try:
        response = requests.post(ORS_API_BASE_URL, headers=headers, json=body)
        response.raise_for_status() # Lança exceção para erros HTTP
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"Erro ao conectar ao OpenRouteService: {e}"
    except json.JSONDecodeError as e:
        return None, f"Erro ao decodificar resposta JSON do OpenRouteService: {e}"

# --- Configuração da Página Streamlit ---
st.set_page_config(page_title="Agente Ciclista Amador", layout="centered")

st.title("🚴 Agente Ciclista Amador 🚴")
st.markdown("Preencha as informações abaixo para receber recomendações personalizadas para o seu pedal!")

# --- Formulário de Entrada do Usuário ---
with st.form("ciclista_form"):
    st.header("Seus Dados de Ciclista")

    col1, col2, col3 = st.columns(3)
    with col1:
        peso = st.number_input("Seu Peso (kg):", min_value=30, max_value=200, value=70, step=1)
    with col2:
        idade = st.number_input("Sua Idade:", min_value=5, max_value=100, value=30, step=1)
    with col3:
        altura = st.number_input("Sua Altura (cm):", min_value=100, max_value=250, value=175, step=1)

    sexo = st.radio(
        "Seu Sexo:",
        options=["Masculino", "Feminino", "Não informar"],
        index=0
    )

    tempo_sem_pedalar = st.selectbox(
        "Há quanto tempo você não pedala?",
        options=["Menos de 1 mês", "1 a 3 meses", "3 a 6 meses", "6 meses a 1 ano", "Mais de 1 ano", "Sou ciclista ativo"],
        index=5
    )

    st.subheader("Sua Bicicleta")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        tipo_bicicleta = st.selectbox(
            "Tipo de Bicicleta:",
            options=["Estrada", "Mountain Bike", "Urbana", "Híbrida", "Fixa"],
            index=1
        )
    with col_b2:
        num_velocidades = st.number_input("Número de Velocidades:", min_value=1, max_value=36, value=21, step=1)

    st.subheader("Sua Rota")
    # Para o ORS, precisamos de coordenadas. Usaremos valores fixos por enquanto ou o Streamlit Maps.
    # A obtenção de coordenadas de endereços é um passo adicional (geocoding API).
    # Por agora, a IA vai estimar as coordenadas ou a rota.
    origem_endereco = st.text_input("Local de Origem (endereço):", value="Buriti Shopping, Av. Rio Verde, Aparecida de Goiânia")
    destino_endereco = st.text_input("Local de Destino (endereço):", value="Abadia de Goiás")
    
    # Placeholder para coordenadas. Em uma versão futura, usaríamos uma Geocoding API.
    # A IA terá que 'imaginar' as coordenadas ou o usuário precisaria fornecê-las.
    # Para fins de teste da API ORS, você pode usar coordenadas conhecidas.
    # Exemplo de coordenadas (Buriti Shopping, Aparecida de Goiânia e Abadia de Goiás)
    # ATENÇÃO: Estes são exemplos. Para precisão, você precisaria de uma API de Geocoding.
    origem_coords = (-16.7456, -49.3245) # Exemplo: Lat/Lon Buriti Shopping
    destino_coords = (-16.8524, -49.4447) # Exemplo: Lat/Lon Abadia de Goiás


    problema_saude = st.text_area(
        "Algum Problema de Saúde? (Ex: Asma, Problemas Cardíacos, Joelho, etc. Se nenhum, deixe vazio):",
        value=""
    )

    finalidade_pedal = st.selectbox(
        "Para qual finalidade você está se preparando para esse pedal?",
        options=["Lazer", "Exercício físico/Saúde", "Deslocamento/Trabalho", "Viagem/Cicloturismo", "Competicao/Evento"],
        index=0
    )

    distancia_meta = None
    prazo_preparacao = None
    alimentacao_sugerida = None

    if finalidade_pedal in ["Viagem/Cicloturismo", "Competicao/Evento"]:
        st.markdown("---")
        st.subheader("Detalhes para Pedal Longo/Preparação")
        col_long1, col_long2 = st.columns(2)
        with col_long1:
            distancia_meta = st.number_input("Distância meta (km):", min_value=10, max_value=1000, value=50, step=5)
        with col_long2:
            prazo_preparacao = st.text_input("Prazo para se preparar (Ex: 3 meses, 8 semanas):", value="Nenhum específico")
        alimentacao_sugerida = st.text_area(
            "Você tem alguma preferência ou restrição alimentar a ser considerada para sua alimentação durante o pedal?",
            value="Nenhuma específica"
        )

    submitted = st.form_submit_button("Consultar Agente")

    # --- Processamento e Exibição da Resposta ---
    if submitted:
        current_date_info = datetime.now().strftime("%d de %B de %Y")

        # --- Chamada à API do OpenRouteService (ANTES de chamar a Gemini) ---
        route_data = None
        route_error = None
        if ORS_API_KEY:
            st.info("Buscando rota detalhada com OpenRouteService...")
            # IMPORTANTE: Para uma aplicação real, você precisaria de uma Geocoding API
            # para converter origem_endereco e destino_endereco em coordenadas (latitude, longitude).
            # Para este exemplo, estamos usando coordenadas fixas de exemplo.
            route_json, route_error = get_ors_route(origem_coords, destino_coords, ORS_API_KEY)
            
            if route_json and 'routes' in route_json and len(route_json['routes']) > 0:
                route_data = route_json['routes'][0]
                st.success("Rota obtida com sucesso do OpenRouteService!")
                
                # Exibir informações básicas da rota obtida
                total_distance_km = route_data['summary']['distance'] / 1000
                total_duration_min = route_data['summary']['duration'] / 60
                st.write(f"**Distância Total (ORS):** {total_distance_km:.2f} km")
                st.write(f"**Tempo Total Estimado (ORS):** {total_duration_min:.0f} minutos")
                
                # Prepara os detalhes da rota para o Gemini
                route_details_for_gemini = "Detalhes da rota obtidos via OpenRouteService:\n"
                route_details_for_gemini += f"- Distância Total: {total_distance_km:.2f} km\n"
                route_details_for_gemini += f"- Tempo Estimado: {total_duration_min:.0f} minutos\n"
                
                # Adiciona as instruções da rota (legs) para o prompt do Gemini
                if 'segments' in route_data:
                    route_details_for_gemini += "\nInstruções de Trechos (Resumido):\n"
                    for segment_idx, segment in enumerate(route_data['segments']):
                        for step_idx, step in enumerate(segment['steps']):
                            route_details_for_gemini += f"- Trecho {segment_idx+1}.{step_idx+1}: {step['instruction']} ({step['distance']:.0f}m, {step['duration']:.0f}s)\n"
                            if step_idx > 5: # Limita para não sobrecarregar o prompt
                                route_details_for_gemini += "... (muitas instruções, resumo)\n"
                                break
                
                route_details_for_gemini += "\nPor favor, use esses detalhes para refinar as sugestões de rota, velocidade e marchas.\n"

            else:
                st.warning(f"Não foi possível obter uma rota detalhada do OpenRouteService. {route_error or 'Nenhuma rota encontrada.'}")
                route_details_for_gemini = "Nenhum detalhe de rota fornecido por API."
                if route_error:
                    st.error(f"Erro ORS: {route_error}")
        else:
            st.info("API Key do OpenRouteService não configurada. A Gemini fará estimativas gerais de rota.")
            route_details_for_gemini = "Nenhum detalhe de rota fornecido por API."

        # --- Construção do Prompt para a Gemini ---
        prompt_para_gemini = f"""
        Você é um agente inteligente e experiente para ciclistas amadores, com foco em segurança, economia de energia e bem-estar.
        Um ciclista deseja uma consulta para uma viagem de bicicleta.
        Contexto atual: Aparecida de Goiânia, Goiás, Brasil. Data da consulta: {current_date_info}.

        Dados do ciclista:
        - Peso: {peso} kg
        - Idade: {idade} anos
        - Altura: {altura} cm
        - Sexo: {sexo}
        - Tempo sem pedalar ativamente: {tempo_sem_pedalar}
        - Problema de saúde: {problema_saude if problema_saude else 'Nenhum'}

        Dados da bicicleta:
        - Tipo: {tipo_bicicleta}
        - Número de velocidades: {num_velocidades}

        Detalhes do pedal:
        - Origem: {origem_endereco}
        - Destino: {destino_endereco}
        - Finalidade do pedal: {finalidade_pedal}

        {route_details_for_gemini} # Inclui os detalhes da rota do ORS, se disponíveis

        """

        # Adiciona detalhes de pedal longo se aplicável
        if distancia_meta is not None:
            prompt_para_gemini += f"""
        Detalhes adicionais para pedal longo/preparação:
        - Distância meta: {distancia_meta} km
        - Prazo para preparação: {prazo_preparacao}
        - Informações alimentares relevantes: {alimentacao_sugerida}
            """

        prompt_para_gemini += f"""

        Com base em todas as informações fornecidas, incluindo os detalhes da rota (se disponíveis), seu conhecimento geral sobre ciclismo, topografia aproximada de Aparecida de Goiânia e arredores, e condições climáticas típicas para a data atual, forneça:
        1.  **Sugestões de Rota e Características:** Descreva uma ou mais opções de rota. **Se houver dados do OpenRouteService, use-os para a rota principal**, detalhando o tipo de terreno (plano, subidas, descidas), presença de ciclovias/estradas seguras, e pontos de referência importantes. Confirme a distância e o tempo estimado de pedal (se fornecidos pelo ORS ou baseados em estimativa).
        2.  **Calibragem dos Pneus:** Com base no peso do ciclista e tipo de bicicleta, sugira a calibragem adequada dos pneus em PSI (libras por polegada quadrada).
        3.  **Velocidade Média Sugerida e Esforço por Trecho:**
            * Indique uma velocidade média geral para o percurso.
            * **Crucial:** Se os detalhes da rota com trechos foram fornecidos, analise os diferentes segmentos e **sugira velocidades e níveis de esforço específicos para cada tipo de trecho** (Ex: "Trecho de subida íngreme: velocidade baixa (8-10 km/h), esforço intenso", "Trecho plano: velocidade moderada (20-25 km/h), esforço leve a moderado").
            * Leve em conta o tempo sem pedalar e qualquer problema de saúde.
        4.  **Marchas Adequadas por Trecho (Dicas Práticas):**
            * Baseado na análise da rota (se disponível por trechos), forneça dicas práticas sobre quais marchas usar em diferentes situações (subidas íngremes, terrenos planos, descidas).
            * Explique a importância da cadência e como usá-la para otimizar o uso das marchas.
        5.  **Melhores Horários:** Com base no clima típico de Aparecida de Goiânia para esta época do ano, e na finalidade do pedal, sugira os melhores horários para iniciar o pedal para evitar o calor excessivo, chuva ou vento forte.
        6.  **Dicas de Preparação e Alimentação:**
            * Para ciclistas que estão voltando a pedalar ou com problemas de saúde: Dicas de aquecimento, alongamento e progressão gradual.
            * Para pedais longos ou de preparação: Sugestões de hidratação, alimentação pré-pedal, durante o pedal e pós-pedal, considerando a distância meta e o prazo de preparação.
            * Dicas gerais de segurança e verificação da bicicleta.

        Estruture sua resposta de forma clara, com subtítulos e bullet points. Use negrito para as seções e pontos chave. Comece com uma saudação amigável e um resumo conciso.
        """

        st.info("Gerando sua análise com Gemini...")
        with st.spinner("Pensando nas melhores rotas e dicas para você..."):
            try:
                response = gemini_model.generate_content(prompt_para_gemini)
                resposta_agente = response.text

                st.subheader("✨ Resposta do Agente:")
                st.markdown(resposta_agente)

            except Exception as e:
                st.error(f"Desculpe, ocorreu um erro ao consultar o agente Gemini. Por favor, tente novamente mais tarde. Erro: {e}")
                print(f"Erro ao chamar Gemini: {e}")