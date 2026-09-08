import re
from datetime import datetime

ROTULOS = [
    'Setor', 'Solicitante', 'Email', 'Tipo da reserva', 'Data da reserva',
    'Horário de início/término', 'Espaço', 'Tipo do evento',
    'Recursos necessários', 'Nome do evento ou da disciplina',
    'Quantidade de alunos', 'Pode ser feito em duplas'
]


def limpar(texto):
    return re.sub(r'\s+', ' ', texto or '').strip()


def extrair_campo(texto, rotulo):
    conhecidos = '|'.join(re.escape(x) for x in ROTULOS if x != rotulo)
    padrao = rf'(?im)^\s*{re.escape(rotulo)}\s*:\s*([\s\S]*?)(?=^\s*(?:{conhecidos})\s*:|\Z)'
    m = re.search(padrao, texto or '', re.MULTILINE | re.DOTALL)
    return limpar(m.group(1)) if m else ''


def normalizar_hora_token(valor):
    valor = limpar(valor).lower().replace('horas', 'h').replace('hora', 'h')
    valor = valor.replace(' ', '')
    m = re.fullmatch(r'(\d{1,2})(?::|h)?(\d{2})?h?', valor)
    if not m:
        return ''
    h = int(m.group(1))
    minuto = int(m.group(2) or 0)
    if h > 23 or minuto > 59:
        return ''
    return f'{h:02d}:{minuto:02d}'


def normalizar_hora(valor):
    """Aceita 09:00h as 12:00h, 09h às 12h, 9:00 - 12:00, etc."""
    valor = (valor or '').lower().replace('–', '-').replace('—', '-')
    valor = re.sub(r'\bàs\b|\bas\b', '-', valor)
    tokens = re.findall(r'(?<!\d)(\d{1,2}(?::\d{2}|h\d{2}|h)?)(?!\d)', valor)
    horas = []
    for token in tokens:
        hora = normalizar_hora_token(token)
        if hora and hora not in horas:
            horas.append(hora)
    return (horas[0], horas[1]) if len(horas) >= 2 else ('', '')


def extrair_datas(valor):
    resultados = []
    for d, m, y in re.findall(r'(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)', valor or ''):
        try:
            dt = datetime(int(y), int(m), int(d))
            resultados.append(dt.strftime('%Y-%m-%d'))
        except ValueError:
            pass
    return resultados


def numero_primeiro(valor):
    m = re.search(r'\d+', valor or '')
    return int(m.group()) if m else ''


def mapear_tipo_evento(valor):
    v = limpar(valor)
    return 'Curso' if v.lower() == 'aula' else v


def mapear_sala(espaco):
    bruto = limpar(espaco)
    v = bruto.lower()
    if re.search(r'laborat[oó]rios?|laborat[oó]rio', v):
        m = re.search(r'laborat[oó]rio\s*(\d{1,2})', v, re.I)
        return ('LABORATORIO', f'{int(m.group(1)):02d}_LAB') if m else ('LABORATORIO', '')
    if 'metodologias ativas' in v:
        return 'MA', '400'
    if re.search(r'audit[oó]rio', v):
        return 'AUDITORIO', 'AUDITÓRIO'
    if re.fullmatch(r'\d{2}_LAB', bruto, re.I):
        return 'LABORATORIO', bruto.upper()
    return '', ''


def dias_semana(datas):
    nomes = {0: 'SEG', 1: 'TER', 2: 'QUA', 3: 'QUI', 4: 'SEX', 5: 'SAB', 6: 'DOM'}
    return list(dict.fromkeys(nomes[datetime.strptime(d, '%Y-%m-%d').weekday()] for d in datas))


def interpretar(texto):
    tipo_reserva = extrair_campo(texto, 'Tipo da reserva')
    data_raw = extrair_campo(texto, 'Data da reserva')
    datas = extrair_datas(data_raw)
    inicio, fim = normalizar_hora(extrair_campo(texto, 'Horário de início/término'))
    espaco = extrair_campo(texto, 'Espaço')
    tipo_sala, sala = mapear_sala(espaco)
    tipo_evento = extrair_campo(texto, 'Tipo do evento')
    recorrente = 'recorr' in tipo_reserva.lower()
    return {
        'tipo_reserva': 'Recorrente' if recorrente else 'Individual',
        'data_inicio': datas[0] if datas else '',
        'data_final': datas[-1] if recorrente and len(datas) > 1 else '',
        'dias_semana': dias_semana(datas) if recorrente else [],
        'hora_inicio': inicio,
        'hora_fim': fim,
        'tipo_sala': tipo_sala,
        'sala': sala,
        'tipo_evento': mapear_tipo_evento(tipo_evento),
        'quantidade_alunos': numero_primeiro(extrair_campo(texto, 'Quantidade de alunos')),
        'solicitante': extrair_campo(texto, 'Solicitante'),
        'email': extrair_campo(texto, 'Email'),
        # Mantém exatamente a informação do Forms para conferência.
        'espaco_original': extrair_campo(texto, 'Espaço'),
        'descricao': extrair_campo(texto, 'Nome do evento ou da disciplina'),
    }
