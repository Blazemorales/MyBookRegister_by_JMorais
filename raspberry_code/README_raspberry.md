# Guia do lado da Pi — variante MQTT

Este guia cobre a parte que roda na **Raspberry Pi** quando você usa a
variante **MQTT** da lâmpada (`esp32s3_mqtt_led.ino`), em vez da variante
web pura. Para a configuração do túnel Cloudflare (comum às duas
variantes), veja o `README.md` na raiz do projeto.

Nessa variante, a Pi tem três papéis:

1. Rodar o **broker MQTT** (mosquitto) — ponto de encontro entre a ESP32 e
   quem manda comandos.
2. Rodar a **API HTTP** (`control_led.py`) — traduz requisições HTTP em
   comandos MQTT, para o Cloudflare Tunnel apontar pra ela em vez de
   direto pra ESP32.
3. (Opcional) Rodar o **watchdog** — loga quando a ESP32 sai/volta do ar.

```
Cloudflare Tunnel ──HTTP──► control_led.py (Flask, :5000) ──MQTT──► mosquitto (:1883) ◄──MQTT── ESP32
```

---

## 1. Broker MQTT (mosquitto)

```bash
bash setup_mosquitto.sh
```

Isso instala o mosquitto, cria `/etc/mosquitto/conf.d/local.conf` (cópia
de referência em `local.conf` neste diretório) liberando a porta 1883 para
qualquer IP da rede local, e sobe o serviço.

> ⚠️ `allow_anonymous true` só é seguro em rede local confiável. Para expor
> a Pi além da rede de casa, crie um usuário com `mosquitto_passwd` e troque
> por `password_file` no `local.conf` (comentário já deixado no script).

Teste rápido:

```bash
mosquitto_sub -h localhost -t 'jmorais/esp32s3/led/#' -v
mosquitto_pub -h localhost -t 'jmorais/esp32s3/led/comando' -m 'ON'
```

Depois de confirmar que o broker responde, valide o caminho completo
(ESP32 já com o firmware MQTT gravado e na mesma rede) com:

```bash
python3 mqtt_test.py            # broker em localhost
python3 mqtt_test.py 192.168.0.42   # broker em outro IP
```

## 2. API de controle (`control_led.py`)

```bash
python3 -m venv /home/pi/MyBookRegister_by_JMorais/venv_led_api
/home/pi/MyBookRegister_by_JMorais/venv_led_api/bin/pip install -r requirements.txt
```

Teste manual (modo Flask dev, porta 5000):

```bash
/home/pi/MyBookRegister_by_JMorais/venv_led_api/bin/python control_led.py
curl http://127.0.0.1:5000/led/state
```

Em produção, use o serviço systemd (roda via gunicorn):

```bash
sudo cp led-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now led-api
sudo systemctl status led-api --no-pager
```

Endpoints:

| Rota | Efeito |
|------|--------|
| `GET /led/on` | Publica `ON` no tópico de comando |
| `GET /led/off` | Publica `OFF` |
| `GET /led/toggle` | Publica `TOGGLE` |
| `GET /led/state` | Retorna `{aceso, online}` (cache atualizado pelos tópicos de estado/LWT) |
| `GET /` | Página HTML mínima com os três botões |

No dashboard do Cloudflare Tunnel, aponte o **Public Hostname** para
`http://127.0.0.1:5000` em vez de para a ESP32 diretamente — assim os
comandos passam pela API/MQTT ao invés de pela página web embutida na
placa.

## 3. Watchdog (opcional)

Loga no journal quando a ESP32 fica online/offline (usa o mesmo tópico de
disponibilidade/LWT que a API já consome):

```bash
sudo cp esp32-watchdog.sh /home/pi/esp32-mqtt/esp32-watchdog.sh
sudo chmod +x /home/pi/esp32-mqtt/esp32-watchdog.sh
sudo cp esp32-watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now esp32-watchdog
journalctl -u esp32-watchdog -f
```

---

## Troubleshooting específico da Pi

| Problema | Solução |
|----------|---------|
| `led-api` não sobe | `journalctl -u led-api -n 50`; confira se o venv em `venv_led_api` existe e tem as libs de `requirements.txt` |
| `/led/state` sempre retorna `aceso: null` | A API ainda não recebeu nenhuma mensagem retida no tópico de estado — publique um comando primeiro, ou confira se a ESP32 está publicando com `retain=true` |
| `/led/state` retorna `online: false` mesmo com a ESP32 ligada | Confira o LWT (Last Will) da ESP32: tópico `jmorais/esp32s3/led/disponibilidade`, payload `online`/`offline` |
| Mosquitto recusa conexão de fora da Pi | Confira `listener 1883 0.0.0.0` em `local.conf` e se o firewall (se houver) libera a porta na rede local |
| Quero MQTT achável de fora de casa | O Cloudflare Tunnel não expõe TCP cru (porta 1883); use a API HTTP (`led-api`) como ponte, ou MQTT sobre WebSockets (listener 9001 no mosquitto) |


# broker
sudo apt install -y mosquitto mosquitto-clients && sudo systemctl enable --now mosquitto
# api
mkdir -p ~/led-api && cd ~/led-api   # copie control_led.py aqui
python3 -m venv .venv && source .venv/bin/activate
pip install flask paho-mqtt gunicorn
# serviço
sudo cp led-api.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl enable --now led-api
curl localhost:5000/led/on
