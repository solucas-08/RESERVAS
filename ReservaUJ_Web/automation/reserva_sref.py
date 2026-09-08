import json
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

URL_LOGIN = "https://app.unijorge.edu.br/sref/Login?ReturnUrl=/sref"
URL_RESERVA = "https://app.unijorge.edu.br/sref/Reserva/Adicionar"


def preencher_input_js(navegador, elemento, valor):
    navegador.execute_script("""
        const elemento = arguments[0];
        const valor = arguments[1];
        elemento.value = valor;
        elemento.dispatchEvent(new Event('input', {bubbles: true}));
        elemento.dispatchEvent(new Event('change', {bubbles: true}));
        elemento.dispatchEvent(new Event('blur', {bubbles: true}));
    """, elemento, valor)


def preencher_hora(navegador, elemento, valor):
    if not valor or len(valor) != 5 or valor[2] != ":":
        raise ValueError(f"Horário inválido: {valor}. Use HH:MM.")
    h, m = int(valor[:2]), int(valor[3:])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Horário inválido: {valor}")
    preencher_input_js(navegador, elemento, valor)
    time.sleep(0.2)
    real = elemento.get_attribute("value")
    if real != valor:
        raise RuntimeError(f"Horário não foi preenchido: esperado {valor}, encontrado {real}")


def preencher_sala(navegador, wait, valor_sala):
    if not valor_sala:
        raise ValueError("Sala SREF não informada.")
    campo = wait.until(EC.presence_of_element_located((By.ID, "sala")))
    existe = navegador.execute_script("""
        const d = document.getElementById('salaOptions');
        if (!d) return false;
        return Array.from(d.querySelectorAll('option')).some(o => o.value === arguments[0]);
    """, valor_sala)
    if not existe:
        opcoes = navegador.execute_script("""
            const d = document.getElementById('salaOptions');
            if (!d) return [];
            return Array.from(d.querySelectorAll('option')).map(o => o.value);
        """)
        raise ValueError(f"Sala '{valor_sala}' não disponível para o tipo selecionado. Opções: {opcoes}")
    campo.clear()
    campo.send_keys(valor_sala)
    navegador.execute_script("""
        const c = arguments[0];
        c.dispatchEvent(new Event('input', {bubbles:true}));
        c.dispatchEvent(new Event('change', {bubbles:true}));
        c.dispatchEvent(new Event('blur', {bubbles:true}));
    """, campo)
    time.sleep(0.4)
    if campo.get_attribute("value") != valor_sala:
        raise RuntimeError(f"Sala não foi preenchida corretamente: {valor_sala}")


def fazer_login(navegador, wait, usuario, senha):
    navegador.get(URL_LOGIN)
    Select(wait.until(EC.presence_of_element_located((By.ID, "LoginViewModel_IES")))).select_by_visible_text("UJ")
    wait.until(EC.presence_of_element_located((By.ID, "LoginViewModel_Login"))).send_keys(usuario)
    wait.until(EC.presence_of_element_located((By.ID, "LoginViewModel_Senha"))).send_keys(senha)
    wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="login_form"]/section[3]/label/button'))).click()
    wait.until(lambda d: "/Login" not in d.current_url)


def marcar_dias(navegador, wait, dias):
    mapa = {"SEG":"seg", "TER":"ter", "QUA":"qua", "QUI":"qui", "SEX":"sex", "SAB":"sab", "DOM":"dom"}
    for dia in dias:
        chave = str(dia).upper().replace("Á", "A")
        if chave not in mapa:
            raise ValueError(f"Dia da semana inválido: {dia}")
        checkbox = wait.until(EC.presence_of_element_located((By.ID, mapa[chave])))
        if not checkbox.is_selected():
            navegador.execute_script("""
                const c = arguments[0];
                c.checked = true;
                c.dispatchEvent(new Event('input', {bubbles:true}));
                c.dispatchEvent(new Event('change', {bubbles:true}));
                c.dispatchEvent(new Event('click', {bubbles:true}));
            """, checkbox)
        if not checkbox.is_selected():
            raise RuntimeError(f"Não foi possível selecionar {dia}")


def preencher_reserva(navegador, wait, reserva):
    # O Selenium usa SOMENTE os campos normalizados abaixo.
    # espaco_original não é usado aqui.
    tipo_sala = reserva.get("tipo_sala", "").strip()
    sala = reserva.get("sala", "").strip()
    if not tipo_sala or not sala:
        raise ValueError("tipo_sala e sala são obrigatórios.")

    Select(wait.until(EC.presence_of_element_located((By.ID, "campus")))).select_by_value("UNIDADE PARALELA")
    Select(wait.until(EC.presence_of_element_located((By.ID, "tipoSala")))).select_by_value(tipo_sala)

    wait.until(lambda d: d.execute_script("""
        const d=document.getElementById('salaOptions');
        return d && d.querySelectorAll('option').length > 0;
    """))

    evento = reserva.get("tipo_evento", "").strip()
    if evento.lower() == "aula":
        evento = "Curso"
    Select(wait.until(EC.presence_of_element_located((By.ID, "idTipoEvento")))).select_by_visible_text(evento)

    tipo_reserva = reserva.get("tipo_reserva", "Individual").strip()
    Select(wait.until(EC.presence_of_element_located((By.ID, "tipoReserva")))).select_by_visible_text(tipo_reserva)

    preencher_input_js(navegador, wait.until(EC.presence_of_element_located((By.ID, "dataInicio"))), reserva["data_inicio"])

    if tipo_reserva == "Recorrente":
        data_final = reserva.get("data_final", "").strip()
        dias = reserva.get("dias_semana", [])
        if not data_final or not dias:
            raise ValueError("Reserva recorrente exige data_final e pelo menos um dia da semana.")
        preencher_input_js(navegador, wait.until(EC.presence_of_element_located((By.NAME, "DataFinalReserva"))), data_final)
        marcar_dias(navegador, wait, dias)

    preencher_hora(navegador, wait.until(EC.presence_of_element_located((By.ID, "horaInicio"))), reserva["hora_inicio"])
    preencher_hora(navegador, wait.until(EC.presence_of_element_located((By.ID, "horaFim"))), reserva["hora_fim"])

    qtd = str(reserva.get("quantidade_alunos", "")).strip()
    if not qtd:
        raise ValueError("Quantidade de alunos não informada.")
    campo_qtd = wait.until(EC.presence_of_element_located((By.ID, "qtdPessoas")))
    campo_qtd.clear(); campo_qtd.send_keys(qtd)

    preencher_sala(navegador, wait, sala)

    reservado = reserva.get("reservado_para") or reserva.get("solicitante") or ""
    campo = wait.until(EC.presence_of_element_located((By.ID, "reservadoPara")))
    campo.clear(); campo.send_keys(reservado)

    descricao = reserva.get("descricao", "")
    campo = wait.until(EC.presence_of_element_located((By.ID, "descricaoReserva")))
    campo.clear(); campo.send_keys(descricao)


def main():
    reserva = json.loads(os.environ["RESERVA_JSON"])
    usuario = os.environ["SREF_USUARIO"]
    senha = os.environ["SREF_SENHA"]
    enviar = os.environ.get("ENVIAR_SOLICITACAO", "false").lower() == "true"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

    navegador = webdriver.Chrome(options=options)
    wait = WebDriverWait(navegador, 30)
    try:
        print("Iniciando login SREF...")
        fazer_login(navegador, wait, usuario, senha)
        print("Login realizado.")
        navegador.get(URL_RESERVA)
        wait.until(lambda d: "/Reserva/Adicionar" in d.current_url)
        preencher_reserva(navegador, wait, reserva)
        navegador.save_screenshot("reserva_preenchida.png")
        print("Preenchimento concluído. Screenshot: reserva_preenchida.png")

        if enviar:
            botao = wait.until(EC.element_to_be_clickable((By.ID, "apukui")))
            botao.click()
            time.sleep(2)
            print("SOLICITAÇÃO ENVIADA AO SREF.")
        else:
            print("MODO TESTE: botão Solicitar NÃO foi clicado.")
    finally:
        navegador.quit()


if __name__ == "__main__":
    main()
