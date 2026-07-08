/*
 * MyBookRegister - Controle de lâmpada 12V DC via relé Songle SRD-05VDC-SL-C
 * - Conecta automaticamente na rede UnB Wireless (WPA2-Enterprise) OU residencial (WPA2-Personal)
 * - Servidor web com UI renovada + cronômetro em tempo real
 * - Cliente MQTT (broker no Raspberry Pi via Cloudflare Tunnel, raspberry.mbrlamp.com.br)
 * - Registra tempo ligada (sessão atual + acumulado persistente em NVS) e publica via MQTT
 *   para o Raspberry Pi coletar os dados (pipeline do CEP)
 *
 * Bibliotecas necessárias (Library Manager):
 *   "PubSubClient" by Nick O'Leary
 *   "DHT sensor library" by Adafruit (+ dependência "Adafruit Unified Sensor")
 *   Preferences.h e WebServer.h já vêm com o core ESP32, não precisa instalar
 */

#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <DHT.h>
#include "esp_wpa2.h"
#include "credenciais.h"

// ================== CONFIGURAÇÃO DO RELÉ ==================
#define RELAY_PIN 4
#define RELAY_ATIVO_LOW true

// ================== CONFIGURAÇÃO DO MQTT ==================
// Broker exposto via Cloudflare Tunnel (TCP direto), sem autenticação
const char* MQTT_BROKER    = "raspberry.mbrlamp.com.br";
const int   MQTT_PORT      = 1883; // ajuste para 8883 se o tunnel expuser com TLS
const char* MQTT_CLIENT_ID = "esp32-mbrlamp";

const char* TOPIC_COMANDO       = "mbrlamp/lampada/comando";        // assina: "ON" / "OFF"
const char* TOPIC_ESTADO        = "mbrlamp/lampada/estado";         // publica: "ON" / "OFF" (retained)
const char* TOPIC_TEMPO_SESSAO  = "mbrlamp/lampada/tempo_sessao_s"; // publica: segundos da sessão atual
const char* TOPIC_TEMPO_TOTAL   = "mbrlamp/lampada/tempo_total_s";  // publica: segundos acumulados (todo tempo)
const char* TOPIC_UMIDADE       = "mbrlamp/ambiente/umidade";       // publica: % umidade relativa
const char* TOPIC_TEMPERATURA   = "mbrlamp/ambiente/temperatura";   // publica: °C

// ================== CONFIGURAÇÃO DO DHT11 ==================
#define DHTPIN 18   // <-- AJUSTE AQUI para o GPIO real usado no seu circuito
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

float ultimaUmidade = NAN;
float ultimaTemperatura = NAN;
unsigned long ultimaLeituraDHT = 0;
const unsigned long INTERVALO_DHT_MS = 5UL * 60UL * 1000UL; // 5 minutos

WiFiClient espClient;
PubSubClient mqttClient(espClient);
WebServer server(80);
Preferences prefs;

enum class ModoRede { NENHUM, ENTERPRISE, PESSOAL };
ModoRede modoAtual = ModoRede::NENHUM;

// ================== CONTROLE DE TEMPO LIGADA ==================
bool relayLigado = false;
unsigned long inicioSessaoMillis = 0;   // millis() de quando ligou a última vez
unsigned long totalAcumuladoSeg = 0;    // segundos acumulados em toda a vida do dispositivo (persistente)
unsigned long ultimaPublicacaoMqtt = 0;
const unsigned long INTERVALO_PUBLICACAO_MS = 5000; // publica estatísticas a cada 5s enquanto ligada

unsigned long segundosSessaoAtual() {
  if (!relayLigado) return 0;
  return (millis() - inicioSessaoMillis) / 1000;
}

void salvarTotalAcumulado() {
  prefs.putULong("total_seg", totalAcumuladoSeg);
}

// ================== RELÉ ==================
void relayOff() {
  digitalWrite(RELAY_PIN, RELAY_ATIVO_LOW ? HIGH : LOW);
  if (relayLigado) {
    totalAcumuladoSeg += segundosSessaoAtual();
    salvarTotalAcumulado();
  }
  relayLigado = false;
}

void relayOn() {
  digitalWrite(RELAY_PIN, RELAY_ATIVO_LOW ? LOW : HIGH);
  if (!relayLigado) {
    inicioSessaoMillis = millis();
  }
  relayLigado = true;
}

// ================== DHT11 (umidade/temperatura) ==================
void lerEPublicarDHT() {
  float umidade = dht.readHumidity();
  float temperatura = dht.readTemperature();

  if (isnan(umidade) || isnan(temperatura)) {
    Serial.println("Falha ao ler o DHT11 (confira fiação/GPIO)");
    return;
  }

  ultimaUmidade = umidade;
  ultimaTemperatura = temperatura;

  Serial.print("DHT11 -> Umidade: "); Serial.print(umidade); Serial.print("%  Temp: ");
  Serial.print(temperatura); Serial.println("C");

  mqttClient.publish(TOPIC_UMIDADE, String(umidade, 1).c_str(), true);
  mqttClient.publish(TOPIC_TEMPERATURA, String(temperatura, 1).c_str(), true);
}

// ================== PÁGINA WEB (UI renovada) ==================
void handleRoot() {
  String html = R"HTML(
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MyBookRegister - Lampada</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
    font-family: 'Segoe UI', Arial, sans-serif;
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: #e2e8f0;
  }
  .card {
    background: #1e293b; border-radius: 20px; padding: 32px 28px; width: 320px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.4); text-align: center;
    border: 1px solid #334155;
  }
  h1 { font-size: 20px; font-weight: 600; margin: 0 0 4px; color: #f1f5f9; }
  .sub { font-size: 12px; color: #94a3b8; margin-bottom: 24px; }
  .bulb {
    width: 90px; height: 90px; border-radius: 50%; margin: 0 auto 20px;
    display: flex; align-items: center; justify-content: center; font-size: 40px;
    transition: all 0.3s ease;
  }
  .bulb.on  { background: radial-gradient(circle, #fde68a, #f59e0b); box-shadow: 0 0 40px #fbbf24; }
  .bulb.off { background: #334155; box-shadow: none; }
  .estado { font-size: 15px; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; }
  .estado.on  { color: #4ade80; }
  .estado.off { color: #f87171; }
  .cronometro {
    font-size: 34px; font-weight: 700; font-variant-numeric: tabular-nums;
    color: #f1f5f9; margin: 10px 0 4px; letter-spacing: 1px;
  }
  .cronometro-label { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }
  .total { font-size: 13px; color: #94a3b8; margin-top: 18px; padding-top: 16px; border-top: 1px solid #334155; }
  .total b { color: #cbd5e1; }
  .ambiente {
    display: flex; gap: 10px; margin-top: 16px;
  }
  .ambiente-card {
    flex: 1; background: #0f172a; border: 1px solid #334155; border-radius: 14px;
    padding: 14px 8px; text-align: center;
  }
  .ambiente-icone { font-size: 22px; margin-bottom: 4px; }
  .ambiente-valor { font-size: 22px; font-weight: 700; color: #f1f5f9; font-variant-numeric: tabular-nums; }
  .ambiente-label { font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }
  .botoes { display: flex; gap: 10px; margin-top: 22px; }
  button {
    flex: 1; padding: 14px 0; border: none; border-radius: 12px; font-size: 15px; font-weight: 700;
    cursor: pointer; transition: transform 0.15s ease, opacity 0.15s ease; color: #fff;
  }
  button:active { transform: scale(0.96); }
  .btn-on  { background: linear-gradient(135deg, #22c55e, #16a34a); }
  .btn-off { background: linear-gradient(135deg, #ef4444, #b91c1c); }
  button:disabled { opacity: 0.4; cursor: default; }
</style>
</head>
<body>
  <div class="card">
    <h1>MyBookRegister</h1>
    <div class="sub">Controle da lâmpada 12V</div>

    <div id="bulb" class="bulb off">💡</div>
    <div id="estadoTexto" class="estado off">DESLIGADA</div>

    <div class="cronometro" id="cronometro">00:00:00</div>
    <div class="cronometro-label">tempo desta sessão</div>

    <div class="total">Tempo total acumulado: <b id="totalTexto">--</b></div>

    <div class="ambiente">
      <div class="ambiente-card">
        <div class="ambiente-icone">💧</div>
        <div class="ambiente-valor" id="umidadeTexto">--</div>
        <div class="ambiente-label">Umidade</div>
      </div>
      <div class="ambiente-card">
        <div class="ambiente-icone">🌡️</div>
        <div class="ambiente-valor" id="temperaturaTexto">--</div>
        <div class="ambiente-label">Temperatura</div>
      </div>
    </div>

    <div class="botoes">
      <button id="btnOn" class="btn-on" onclick="enviar('/on')">LIGAR</button>
      <button id="btnOff" class="btn-off" onclick="enviar('/off')">DESLIGAR</button>
    </div>
  </div>

<script>
let ligado = false;
let segundosSessaoBase = 0;
let referenciaLocal = performance.now();

function formatarHMS(totalSegundos) {
  const h = Math.floor(totalSegundos / 3600);
  const m = Math.floor((totalSegundos % 3600) / 60);
  const s = Math.floor(totalSegundos % 60);
  return [h, m, s].map(v => String(v).padStart(2, '0')).join(':');
}

function atualizarTela(estado, segSessao, segTotal, umidade, temperatura) {
  ligado = (estado === 'ON');
  segundosSessaoBase = segSessao;
  referenciaLocal = performance.now();

  document.getElementById('bulb').className = 'bulb ' + (ligado ? 'on' : 'off');
  document.getElementById('estadoTexto').className = 'estado ' + (ligado ? 'on' : 'off');
  document.getElementById('estadoTexto').textContent = ligado ? 'LIGADA' : 'DESLIGADA';
  document.getElementById('btnOn').disabled = ligado;
  document.getElementById('btnOff').disabled = !ligado;
  document.getElementById('totalTexto').textContent = formatarHMS(segTotal);
  document.getElementById('umidadeTexto').textContent = (umidade >= 0) ? umidade + '%' : '--';
  document.getElementById('temperaturaTexto').textContent = (temperatura > -273) ? temperatura + '°C' : '--';
}

async function consultarStatus() {
  try {
    const r = await fetch('/api/status');
    const j = await r.json();
    atualizarTela(j.estado, j.tempo_sessao_s, j.tempo_total_s, j.umidade, j.temperatura);
  } catch (e) { /* falha de rede momentânea, tenta de novo no próximo ciclo */ }
}

async function enviar(caminho) {
  await fetch(caminho);
  consultarStatus();
}

// Cronômetro visual local, atualizado a cada segundo sem precisar do servidor
setInterval(() => {
  if (ligado) {
    const decorridoLocal = (performance.now() - referenciaLocal) / 1000;
    document.getElementById('cronometro').textContent = formatarHMS(segundosSessaoBase + decorridoLocal);
  } else {
    document.getElementById('cronometro').textContent = '00:00:00';
  }
}, 1000);

// Resincroniza com o ESP32 periodicamente (pega mudanças feitas via MQTT também)
setInterval(consultarStatus, 4000);
consultarStatus();
</script>
</body></html>
)HTML";

  server.send(200, "text/html", html);
}

void handleStatusApi() {
  String json = "{";
  json += "\"estado\":\"" + String(relayLigado ? "ON" : "OFF") + "\",";
  json += "\"tempo_sessao_s\":" + String(segundosSessaoAtual()) + ",";
  json += "\"tempo_total_s\":" + String(totalAcumuladoSeg + segundosSessaoAtual()) + ",";
  json += "\"umidade\":" + String(isnan(ultimaUmidade) ? -1 : ultimaUmidade, 1) + ",";
  json += "\"temperatura\":" + String(isnan(ultimaTemperatura) ? -1 : ultimaTemperatura, 1);
  json += "}";
  server.send(200, "application/json", json);
}

void publicarEstadoMqtt() {
  mqttClient.publish(TOPIC_ESTADO, relayLigado ? "ON" : "OFF", true);
}

void handleOn() {
  relayOn();
  Serial.println("Lâmpada LIGADA (via navegador)");
  publicarEstadoMqtt();
  server.send(200, "text/plain", "ok");
}

void handleOff() {
  relayOff();
  Serial.println("Lâmpada DESLIGADA (via navegador)");
  publicarEstadoMqtt();
  server.send(200, "text/plain", "ok");
}

// ================== MQTT ==================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String mensagem;
  for (unsigned int i = 0; i < length; i++) mensagem += (char)payload[i];

  Serial.print("MQTT recebido ["); Serial.print(topic); Serial.print("]: "); Serial.println(mensagem);

  if (String(topic) == TOPIC_COMANDO) {
    if (mensagem == "ON") {
      relayOn();
      publicarEstadoMqtt();
    } else if (mensagem == "OFF") {
      relayOff();
      publicarEstadoMqtt();
    }
  }
}

void conectarMqtt() {
  if (mqttClient.connected()) return;

  Serial.print("Conectando ao broker MQTT ("); Serial.print(MQTT_BROKER); Serial.print(")... ");
  if (mqttClient.connect(MQTT_CLIENT_ID)) {
    Serial.println("conectado!");
    mqttClient.subscribe(TOPIC_COMANDO);
    publicarEstadoMqtt();
  } else {
    Serial.print("falhou, rc="); Serial.println(mqttClient.state());
  }
}

// ================== WIFI ==================
bool redeVisivel(const char* alvo) {
  int total = WiFi.scanComplete();
  for (int i = 0; i < total; i++) if (WiFi.SSID(i) == alvo) return true;
  return false;
}

bool tentarConectarEnterprise() {
  Serial.print("Tentando UNB Wireless (WPA2-Enterprise) - "); Serial.println(ssid);
  WiFi.disconnect(true, true);
  delay(200);
  WiFi.mode(WIFI_STA);
  esp_wifi_sta_wpa2_ent_set_identity((uint8_t *)EAP_IDENTITY, strlen(EAP_IDENTITY));
  esp_wifi_sta_wpa2_ent_set_username((uint8_t *)EAP_USERNAME, strlen(EAP_USERNAME));
  esp_wifi_sta_wpa2_ent_set_password((uint8_t *)EAP_PASSWORD, strlen(EAP_PASSWORD));
  esp_wifi_sta_wpa2_ent_enable();
  WiFi.begin(ssid);

  int tentativas = 0;
  while (WiFi.status() != WL_CONNECTED && tentativas < 40) {
    delay(500); Serial.print("."); tentativas++;
  }
  Serial.println();
  return WiFi.status() == WL_CONNECTED;
}

bool tentarConectarPessoal() {
  Serial.print("Tentando rede residencial (WPA2-Personal) - "); Serial.println(WIFI_SSID_CASA);
  WiFi.disconnect(true, true);
  delay(200);
  esp_wifi_sta_wpa2_ent_disable();
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID_CASA, WIFI_PASSWORD_CASA);

  int tentativas = 0;
  while (WiFi.status() != WL_CONNECTED && tentativas < 40) {
    delay(500); Serial.print("."); tentativas++;
  }
  Serial.println();
  return WiFi.status() == WL_CONNECTED;
}

void conectarWifi() {
  Serial.println("Escaneando redes disponíveis...");
  WiFi.mode(WIFI_STA);
  int encontradas = WiFi.scanNetworks();

  bool unbVisivel  = redeVisivel(ssid);
  bool casaVisivel = redeVisivel(WIFI_SSID_CASA);
  WiFi.scanDelete();

  if (encontradas <= 0 || (!unbVisivel && !casaVisivel)) {
    unbVisivel = casaVisivel = true; // scan falhou/rede oculta: tenta as duas mesmo assim
  }

  modoAtual = ModoRede::NENHUM;
  if (unbVisivel && tentarConectarEnterprise()) {
    modoAtual = ModoRede::ENTERPRISE;
  } else if (casaVisivel && tentarConectarPessoal()) {
    modoAtual = ModoRede::PESSOAL;
  }

  if (modoAtual != ModoRede::NENHUM) {
    Serial.print("Conectado! Acesse pelo navegador: http://");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("Falha ao conectar em qualquer rede conhecida.");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  prefs.begin("mbrlamp", false);
  totalAcumuladoSeg = prefs.getULong("total_seg", 0);

  pinMode(RELAY_PIN, OUTPUT);
  relayOff();

  dht.begin();

  conectarWifi();

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);

  server.on("/", handleRoot);
  server.on("/on", handleOn);
  server.on("/off", handleOff);
  server.on("/api/status", handleStatusApi);
  server.begin();
  Serial.println("Servidor web iniciado.");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi caiu, reconectando...");
    conectarWifi();
  }

  if (!mqttClient.connected()) {
    conectarMqtt();
  }
  mqttClient.loop();

  server.handleClient();

  // Publica estatísticas de tempo periodicamente enquanto a lâmpada estiver ligada,
  // para o Raspberry Pi coletar os dados (pipeline do CEP)
  if (relayLigado && millis() - ultimaPublicacaoMqtt > INTERVALO_PUBLICACAO_MS) {
    mqttClient.publish(TOPIC_TEMPO_SESSAO, String(segundosSessaoAtual()).c_str());
    mqttClient.publish(TOPIC_TEMPO_TOTAL, String(totalAcumuladoSeg + segundosSessaoAtual()).c_str());
    ultimaPublicacaoMqtt = millis();
  }

  // Leitura do DHT11 a cada 5 minutos (independe do estado da lâmpada)
  if (millis() - ultimaLeituraDHT > INTERVALO_DHT_MS || ultimaLeituraDHT == 0) {
    lerEPublicarDHT();
    ultimaLeituraDHT = millis();
  }

  // Controle via Serial continua disponível
  if (Serial.available()) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();
    if (comando == "on") { relayOn(); publicarEstadoMqtt(); Serial.println("Lâmpada LIGADA (via serial)"); }
    else if (comando == "off") { relayOff(); publicarEstadoMqtt(); Serial.println("Lâmpada DESLIGADA (via serial)"); }
  }
}