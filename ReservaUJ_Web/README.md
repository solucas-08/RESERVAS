# Reserva UJ — Web + GitHub Actions V4

Esta versão usa a interface web para interpretar/editar a reserva e usa o código Selenium validado no SREF dentro do GitHub Actions.

## Fluxo

Outlook → copiar e-mail → `web/index.html` → INTERPRETAR → editar → REALIZAR → GitHub Actions → Selenium → SREF.

## Importante sobre sala

`espaco_original` é somente informativo e **não é usado pelo Selenium**.
O Selenium usa exclusivamente `tipo_sala` e `sala`, ou seja, os valores editados pelo funcionário.

## Secrets

No repositório GitHub, criar:

- `SREF_USUARIO`
- `SREF_SENHA`

## Teste seguro

O workflow possui a entrada `enviar_solicitacao`.

- `false`: abre login, preenche a reserva e gera screenshot, sem clicar em `Solicitar`.
- `true`: após validar o preenchimento, clica no botão `Solicitar` (`id=apukui`).

Recomenda-se primeiro testar com `false`.

## Próxima integração

O botão `REALIZAR` da página ainda precisa de uma ponte segura para disparar o workflow (sem colocar token do GitHub no HTML). O Power Automate é uma opção adequada para essa ponte.
