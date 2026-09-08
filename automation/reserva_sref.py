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

        elemento.dispatchEvent(
            new Event('input', {bubbles: true})
        );

        elemento.dispatchEvent(
            new Event('change', {bubbles: true})
        );

        elemento.dispatchEvent(
            new Event('blur', {bubbles: true})
        );
    """, elemento, valor)


def preencher_hora(navegador, elemento, valor):
    if not valor or len(valor) != 5 or valor[2] != ":":
        raise ValueError(
            f"Horário inválido: {valor}. Use HH:MM."
        )

    h, m = int(valor[:2]), int(valor[3:])

    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(
            f"Horário inválido: {valor}"
        )

    preencher_input_js(
        navegador,
        elemento,
        valor
    )

    time.sleep(0.2)

    real = elemento.get_attribute("value")

    if real != valor:
        raise RuntimeError(
            f"Horário não foi preenchido: "
            f"esperado {valor}, encontrado {real}"
        )


def preencher_sala(navegador, wait, valor_sala):
    if not valor_sala:
        raise ValueError(
            "Sala SREF não informada."
        )

    campo = wait.until(
        EC.presence_of_element_located(
            (By.ID, "sala")
        )
    )

    # Verifica se a sala existe nas opções
    # carregadas pelo SREF.
    existe = navegador.execute_script("""
        const d = document.getElementById(
            'salaOptions'
        );

        if (!d) {
            return false;
        }

        return Array.from(
            d.querySelectorAll('option')
        ).some(
            o => o.value === arguments[0]
        );
    """, valor_sala)

    if not existe:

        opcoes = navegador.execute_script("""
            const d = document.getElementById(
                'salaOptions'
            );

            if (!d) {
                return [];
            }

            return Array.from(
                d.querySelectorAll('option')
            ).map(
                o => o.value
            );
        """)

        raise ValueError(
            f"Sala '{valor_sala}' não disponível "
            f"para o tipo selecionado. "
            f"Opções disponíveis: {opcoes}"
        )

    campo.clear()

    campo.send_keys(
        valor_sala
    )

    navegador.execute_script("""
        const c = arguments[0];

        c.dispatchEvent(
            new Event(
                'input',
                {bubbles:true}
            )
        );

        c.dispatchEvent(
            new Event(
                'change',
                {bubbles:true}
            )
        );

        c.dispatchEvent(
            new Event(
                'blur',
                {bubbles:true}
            )
        );
    """, campo)

    # Dá tempo para o SREF consultar os dados
    # da sala e atualizar os campos dependentes.
    time.sleep(1)

    valor_real = campo.get_attribute(
        "value"
    )

    if valor_real != valor_sala:
        raise RuntimeError(
            f"Sala não foi preenchida corretamente. "
            f"Esperado: {valor_sala}. "
            f"Encontrado: {valor_real}"
        )

    print(
        f"Sala SREF selecionada: {valor_sala}"
    )


def obter_capacidade_sala(
    navegador,
    wait
):
    """
    Obtém a capacidade da sala diretamente
    do campo que o próprio SREF preenche:

        id="qtdParticipantes"

    Esse campo é readonly e representa a capacidade
    retornada pelo próprio sistema/banco do SREF.

    O código NÃO possui uma tabela de capacidades.
    """

    campo_capacidade = wait.until(
        EC.presence_of_element_located(
            (By.ID, "qtdParticipantes")
        )
    )

    print(
        "Aguardando o SREF carregar "
        "a capacidade da sala..."
    )

    def capacidade_carregada(driver):

        valor = (
            campo_capacidade
            .get_attribute("value")
            or ""
        ).strip()

        if valor:
            return valor

        return False

    valor = wait.until(
        capacidade_carregada
    )

    print(
        f"Valor de capacidade retornado "
        f"pelo SREF: {valor}"
    )

    # Mantém somente os números.
    valor_limpo = "".join(
        c
        for c in str(valor)
        if c.isdigit()
    )

    if not valor_limpo:
        raise ValueError(
            f"Não foi possível interpretar "
            f"a capacidade da sala: {valor}"
        )

    capacidade = int(
        valor_limpo
    )

    if capacidade <= 0:
        raise ValueError(
            f"Capacidade inválida: {capacidade}"
        )

    print(
        f"Capacidade da sala: {capacidade}"
    )

    return capacidade


def ajustar_quantidade_pela_capacidade(
    navegador,
    wait,
    quantidade_solicitada
):
    """
    Compara a quantidade solicitada com a capacidade
    que o próprio SREF retornou.

    Exemplo:

        Solicitado = 70
        Capacidade = 50

        Resultado = 50

    Se:

        Solicitado = 40
        Capacidade = 50

        Resultado = 40
    """

    if quantidade_solicitada is None:
        raise ValueError(
            "Quantidade de alunos não informada."
        )

    quantidade_solicitada = str(
        quantidade_solicitada
    ).strip()

    if not quantidade_solicitada:
        raise ValueError(
            "Quantidade de alunos não informada."
        )

    try:

        quantidade_solicitada = int(
            quantidade_solicitada
        )

    except ValueError:

        raise ValueError(
            f"Quantidade inválida: "
            f"{quantidade_solicitada}"
        )

    if quantidade_solicitada <= 0:
        raise ValueError(
            "Quantidade de alunos deve ser "
            "maior que zero."
        )

    print(
        f"Quantidade solicitada: "
        f"{quantidade_solicitada}"
    )

    # A capacidade vem do próprio SREF.
    capacidade = obter_capacidade_sala(
        navegador,
        wait
    )

    # Regra:
    # nunca informar no SREF uma quantidade
    # maior que a capacidade da sala.
    quantidade_final = min(
        quantidade_solicitada,
        capacidade
    )

    if quantidade_solicitada > capacidade:

        print(
            "ATENÇÃO:"
        )

        print(
            "A quantidade solicitada "
            "é maior que a capacidade da sala."
        )

        print(
            f"Ajustando de "
            f"{quantidade_solicitada} "
            f"para {capacidade}."
        )

    else:

        print(
            "Quantidade dentro da capacidade "
            "da sala."
        )

    campo_qtd = wait.until(
        EC.presence_of_element_located(
            (By.ID, "qtdPessoas")
        )
    )

    campo_qtd.clear()

    campo_qtd.send_keys(
        str(quantidade_final)
    )

    time.sleep(0.3)

    valor_real = (
        campo_qtd
        .get_attribute("value")
    )

    if valor_real != str(
        quantidade_final
    ):
        raise RuntimeError(
            f"Quantidade não foi preenchida "
            f"corretamente. "
            f"Esperado: {quantidade_final}. "
            f"Encontrado: {valor_real}"
        )

    print(
        f"Quantidade final preenchida "
        f"no SREF: {quantidade_final}"
    )

    return quantidade_final


def fazer_login(
    navegador,
    wait,
    usuario,
    senha
):

    print(
        "Abrindo página de login..."
    )

    navegador.get(
        URL_LOGIN
    )

    # IES
    select_ies = wait.until(
        EC.presence_of_element_located(
            (By.ID, "LoginViewModel_IES")
        )
    )

    Select(
        select_ies
    ).select_by_visible_text(
        "UJ"
    )

    # Usuário
    campo_usuario = wait.until(
        EC.presence_of_element_located(
            (By.ID, "LoginViewModel_Login")
        )
    )

    campo_usuario.send_keys(
        usuario
    )

    # Senha
    campo_senha = wait.until(
        EC.presence_of_element_located(
            (By.ID, "LoginViewModel_Senha")
        )
    )

    campo_senha.send_keys(
        senha
    )

    # Entrar
    botao_entrar = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                '//*[@id="login_form"]/section[3]/label/button'
            )
        )
    )

    botao_entrar.click()

    wait.until(
        lambda d:
        "/Login" not in d.current_url
    )

    print(
        "Login realizado com sucesso."
    )


def marcar_dias(
    navegador,
    wait,
    dias
):

    mapa = {
        "SEG": "seg",
        "TER": "ter",
        "QUA": "qua",
        "QUI": "qui",
        "SEX": "sex",
        "SAB": "sab",
        "DOM": "dom"
    }

    for dia in dias:

        chave = (
            str(dia)
            .upper()
            .strip()
        )

        chave = (
            chave
            .replace("Á", "A")
            .replace("É", "E")
            .replace("Í", "I")
            .replace("Ó", "O")
            .replace("Ú", "U")
        )

        if chave not in mapa:
            raise ValueError(
                f"Dia da semana inválido: {dia}"
            )

        checkbox = wait.until(
            EC.presence_of_element_located(
                (By.ID, mapa[chave])
            )
        )

        if not checkbox.is_selected():

            navegador.execute_script("""
                const checkbox = arguments[0];

                checkbox.checked = true;

                checkbox.dispatchEvent(
                    new Event(
                        'input',
                        { bubbles: true }
                    )
                );

                checkbox.dispatchEvent(
                    new Event(
                        'change',
                        { bubbles: true }
                    )
                );

                checkbox.dispatchEvent(
                    new Event(
                        'click',
                        { bubbles: true }
                    )
                );
            """, checkbox)

        if not checkbox.is_selected():

            raise RuntimeError(
                f"Não foi possível selecionar "
                f"o dia {dia}"
            )

        print(
            f"Dia selecionado: {dia}"
        )


def preencher_reserva(
    navegador,
    wait,
    reserva
):

    # =========================================================
    # IMPORTANTE
    #
    # espaco_original NÃO é utilizado pelo Selenium.
    #
    # O Selenium utiliza somente:
    #
    #   tipo_sala
    #   sala
    #
    # Portanto o funcionário pode alterar a Sala SREF
    # independentemente do espaço original informado.
    # =========================================================

    tipo_sala = str(
        reserva.get(
            "tipo_sala",
            ""
        )
    ).strip()

    sala = str(
        reserva.get(
            "sala",
            ""
        )
    ).strip()

    if not tipo_sala:
        raise ValueError(
            "Tipo de sala não informado."
        )

    if not sala:
        raise ValueError(
            "Sala SREF não informada."
        )

    print(
        f"Tipo de sala: {tipo_sala}"
    )

    print(
        f"Sala SREF: {sala}"
    )

    # =========================================================
    # CAMPUS
    # =========================================================

    select_campus = wait.until(
        EC.presence_of_element_located(
            (By.ID, "campus")
        )
    )

    Select(
        select_campus
    ).select_by_value(
        "UNIDADE PARALELA"
    )

    print(
        "Campus: UNIDADE PARALELA"
    )

    # =========================================================
    # TIPO DE SALA
    # =========================================================

    select_tipo_sala = wait.until(
        EC.presence_of_element_located(
            (By.ID, "tipoSala")
        )
    )

    Select(
        select_tipo_sala
    ).select_by_value(
        tipo_sala
    )

    print(
        f"Tipo de sala selecionado: "
        f"{tipo_sala}"
    )

    # Aguarda as opções de sala
    # serem carregadas.
    wait.until(
        lambda d:
        d.execute_script("""
            const lista =
                document.getElementById(
                    'salaOptions'
                );

            return lista &&
                lista.querySelectorAll(
                    'option'
                ).length > 0;
        """)
    )

    time.sleep(0.5)

    # =========================================================
    # TIPO DE EVENTO
    # =========================================================

    evento = str(
        reserva.get(
            "tipo_evento",
            ""
        )
    ).strip()

    if not evento:
        raise ValueError(
            "Tipo de evento não informado."
        )

    # Regra definida:
    #
    # Aula -> Curso
    #
    if evento.lower() == "aula":

        evento = "Curso"

        print(
            "Evento 'Aula' convertido "
            "para 'Curso'."
        )

    select_evento = wait.until(
        EC.presence_of_element_located(
            (By.ID, "idTipoEvento")
        )
    )

    Select(
        select_evento
    ).select_by_visible_text(
        evento
    )

    print(
        f"Tipo de evento: {evento}"
    )

    # =========================================================
    # TIPO DE RESERVA
    # =========================================================

    tipo_reserva = str(
        reserva.get(
            "tipo_reserva",
            "Individual"
        )
    ).strip()

    select_tipo_reserva = wait.until(
        EC.presence_of_element_located(
            (By.ID, "tipoReserva")
        )
    )

    Select(
        select_tipo_reserva
    ).select_by_visible_text(
        tipo_reserva
    )

    print(
        f"Tipo de reserva: {tipo_reserva}"
    )

    # =========================================================
    # DATA INICIAL
    # =========================================================

    data_inicio = str(
        reserva.get(
            "data_inicio",
            ""
        )
    ).strip()

    if not data_inicio:
        raise ValueError(
            "Data inicial não informada."
        )

    campo_data_inicio = wait.until(
        EC.presence_of_element_located(
            (By.ID, "dataInicio")
        )
    )

    preencher_input_js(
        navegador,
        campo_data_inicio,
        data_inicio
    )

    print(
        f"Data inicial: {data_inicio}"
    )

    # =========================================================
    # RECORRENTE
    # =========================================================

    if tipo_reserva.lower() == "recorrente":

        data_final = str(
            reserva.get(
                "data_final",
                ""
            )
        ).strip()

        dias = reserva.get(
            "dias_semana",
            []
        )

        if not data_final:
            raise ValueError(
                "Reserva recorrente exige "
                "data final."
            )

        if not dias:
            raise ValueError(
                "Reserva recorrente exige "
                "pelo menos um dia da semana."
            )

        campo_data_final = wait.until(
            EC.presence_of_element_located(
                (
                    By.NAME,
                    "DataFinalReserva"
                )
            )
        )

        preencher_input_js(
            navegador,
            campo_data_final,
            data_final
        )

        print(
            f"Data final: {data_final}"
        )

        marcar_dias(
            navegador,
            wait,
            dias
        )

    # =========================================================
    # HORA INICIAL
    # =========================================================

    hora_inicio = str(
        reserva.get(
            "hora_inicio",
            ""
        )
    ).strip()

    campo_hora_inicio = wait.until(
        EC.presence_of_element_located(
            (By.ID, "horaInicio")
        )
    )

    preencher_hora(
        navegador,
        campo_hora_inicio,
        hora_inicio
    )

    print(
        f"Hora início: {hora_inicio}"
    )

    # =========================================================
    # HORA FINAL
    # =========================================================

    hora_fim = str(
        reserva.get(
            "hora_fim",
            ""
        )
    ).strip()

    campo_hora_fim = wait.until(
        EC.presence_of_element_located(
            (By.ID, "horaFim")
        )
    )

    preencher_hora(
        navegador,
        campo_hora_fim,
        hora_fim
    )

    print(
        f"Hora fim: {hora_fim}"
    )

    # =========================================================
    # SALA SREF
    # =========================================================

    # Primeiro selecionamos a sala.
    #
    # Isso faz o SREF carregar do próprio sistema
    # a capacidade correspondente àquela sala.

    preencher_sala(
        navegador,
        wait,
        sala
    )

    # =========================================================
    # QUANTIDADE DE PESSOAS
    # =========================================================

    quantidade_solicitada = reserva.get(
        "quantidade_alunos",
        ""
    )

    quantidade_final = (
        ajustar_quantidade_pela_capacidade(
            navegador,
            wait,
            quantidade_solicitada
        )
    )

    # =========================================================
    # RESERVADO PARA
    # =========================================================

    reservado_para = (
        reserva.get(
            "reservado_para"
        )
        or reserva.get(
            "solicitante"
        )
        or ""
    )

    reservado_para = str(
        reservado_para
    ).strip()

    campo_reservado = wait.until(
        EC.presence_of_element_located(
            (By.ID, "reservadoPara")
        )
    )

    campo_reservado.clear()

    campo_reservado.send_keys(
        reservado_para
    )

    print(
        f"Reservado para: "
        f"{reservado_para}"
    )

    # =========================================================
    # DESCRIÇÃO
    # =========================================================

    descricao = str(
        reserva.get(
            "descricao",
            ""
        )
    )

    campo_descricao = wait.until(
        EC.presence_of_element_located(
            (By.ID, "descricaoReserva")
        )
    )

    campo_descricao.clear()

    campo_descricao.send_keys(
        descricao
    )

    print(
        "Descrição preenchida."
    )

    print(
        "======================================"
    )

    print(
        "RESERVA PREENCHIDA"
    )

    print(
        f"Quantidade solicitada: "
        f"{quantidade_solicitada}"
    )

    print(
        f"Quantidade final no SREF: "
        f"{quantidade_final}"
    )

    print(
        "======================================"
    )


def main():

    # =========================================================
    # DADOS
    # =========================================================

    reserva_json = os.environ.get(
        "RESERVA_JSON"
    )

    if not reserva_json:
        raise ValueError(
            "RESERVA_JSON não foi informado."
        )

    reserva = json.loads(
        reserva_json
    )

    usuario = os.environ.get(
        "SREF_USUARIO"
    )

    senha = os.environ.get(
        "SREF_SENHA"
    )

    if not usuario:
        raise ValueError(
            "Secret SREF_USUARIO não configurado."
        )

    if not senha:
        raise ValueError(
            "Secret SREF_SENHA não configurado."
        )

    enviar = (
        os.environ.get(
            "ENVIAR_SOLICITACAO",
            "false"
        ).lower()
        == "true"
    )

    # =========================================================
    # CHROME
    # =========================================================

    options = webdriver.ChromeOptions()

    options.add_argument(
        "--headless=new"
    )

    options.add_argument(
        "--no-sandbox"
    )

    options.add_argument(
        "--disable-dev-shm-usage"
    )

    options.add_argument(
        "--disable-gpu"
    )

    options.add_argument(
        "--window-size=1920,1080"
    )

    options.add_argument(
        "--user-agent="
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 "
        "Safari/537.36"
    )

    navegador = webdriver.Chrome(
        options=options
    )

    wait = WebDriverWait(
        navegador,
        30
    )

    try:

        # =====================================================
        # LOGIN
        # =====================================================

        fazer_login(
            navegador,
            wait,
            usuario,
            senha
        )

        # =====================================================
        # PÁGINA DE RESERVA
        # =====================================================

        print(
            "Abrindo página de reserva..."
        )

        navegador.get(
            URL_RESERVA
        )

        wait.until(
            lambda d:
            "/Reserva/Adicionar"
            in d.current_url
        )

        print(
            "Página de reserva aberta."
        )

        # =====================================================
        # PREENCHER
        # =====================================================

        preencher_reserva(
            navegador,
            wait,
            reserva
        )

        # =====================================================
        # PRINT
        # =====================================================

        navegador.save_screenshot(
            "reserva_preenchida.png"
        )

        print(
            "Screenshot salvo: "
            "reserva_preenchida.png"
        )

        # =====================================================
        # ENVIO
        # =====================================================

        if enviar:

            print(
                "ENVIAR_SOLICITACAO=true"
            )

            print(
                "Clicando em Solicitar..."
            )

            botao_solicitar = wait.until(
                EC.element_to_be_clickable(
                    (By.ID, "apukui")
                )
            )

            botao_solicitar.click()

            time.sleep(2)

            print(
                "SOLICITAÇÃO ENVIADA AO SREF."
            )

        else:

            print(
                "======================================"
            )

            print(
                "MODO TESTE"
            )

            print(
                "O botão 'Solicitar' NÃO foi clicado."
            )

            print(
                "Nenhuma solicitação foi enviada."
            )

            print(
                "======================================"
            )

    except Exception as erro:

        print(
            "======================================"
        )

        print(
            "ERRO NA AUTOMAÇÃO"
        )

        print(
            str(erro)
        )

        print(
            "======================================"
        )

        try:

            navegador.save_screenshot(
                "reserva_erro.png"
            )

            print(
                "Screenshot de erro salvo."
            )

        except Exception as screenshot_erro:

            print(
                "Não foi possível salvar "
                "o screenshot de erro:"
            )

            print(
                str(screenshot_erro)
            )

        raise

    finally:

        navegador.quit()


if __name__ == "__main__":
    main()
