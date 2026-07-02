/*
 * ============================================================================
 * Servidor Web — Controle de Lâmpada DC 12V  |  ESP32-S3-N16R8
 * Redes UnB: eduroam / UNB Wireless (WPA2-Enterprise PEAP/MSCHAPv2)
 * ============================================================================
 */

#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>

// ============================================================================
//  CONFIGURAÇÃO REDES UnB - WPA2-Enterprise (PEAP/MSCHAPv2)
//  Conforme o manual da UnB:
//   - eduroam:      usuário = e-mail completo (matricula@aluno.unb.br)
//   - UNB Wireless: usuário = matrícula sem @aluno.unb.br
//   - Identidade anônima em branco, sem certificado CA, MSCHAPv2
// ============================================================================
const char* MATRICULA    = "***REMOVIDO***";
const char* EAP_PASSWORD = "***REMOVIDO***";  // senha do domínio UnB (mesma do e-mail/SIGAA)

struct RedeUnB {
  const char* ssid;
  String      usuario;
};

RedeUnB REDES[] = {
  { "eduroam",      String(MATRICULA) + "@aluno.unb.br" },  // e-mail completo
  { "UNB Wireless", String(MATRICULA) },                    // só a matrícula
};
const int NUM_REDES = sizeof(REDES) / sizeof(REDES[0]);
int redeAtual = 0;

const char* HOSTNAME      = "lampada";  // acesso por http://lampada.local
// IP da Raspberry Pi rodando lampada_stats.py (reserve o IP dela no DHCP).
// Veja README.md ("Estatísticas de uso") — recurso opcional.
const char* RASPBERRY_URL = "http://192.168.0.50:5000/lampada";

const uint8_t PINO_LED       = 12;     // GPIO ligado ao PC817
const bool    LED_ATIVO_ALTO = true;  // HIGH liga

// ============================================================================
//  ESTADO INTERNO
// ============================================================================
WebServer server(80);
bool estadoLed = false;
unsigned long instanteLigou = 0;
unsigned long ultimaTentativaWiFi = 0;
const unsigned long INTERVALO_RECONEXAO_WIFI = 10000;

unsigned long segundosLigada() {
  return estadoLed ? (millis() - instanteLigou) / 1000 : 0;
}

// ============================================================================
//  ENVIO PARA A RASPBERRY PI
// ============================================================================
void enviarParaRaspberry() {
  if (WiFi.status() != WL_CONNECTED) return;

  String payload = String("{\"aceso\":") + (estadoLed ? "true" : "false")
                 + ",\"ligadoHa\":" + segundosLigada() + "}";

  HTTPClient http;
  http.begin(RASPBERRY_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(2000);  // recurso opcional: não trava o botão se a Pi estiver fora
  int codigo = http.POST(payload);

  if (codigo > 0) {
    Serial.printf("[RPi ] POST %s -> HTTP %d\n", payload.c_str(), codigo);
  } else {
    Serial.printf("[RPi ] Falha no POST: %s\n", http.errorToString(codigo).c_str());
  }
  http.end();
}

// ============================================================================
//  HARDWARE
// ============================================================================
void aplicarEstado(bool aceso) {
  if (aceso && !estadoLed) instanteLigou = millis();
  estadoLed = aceso;
  bool nivel = LED_ATIVO_ALTO ? aceso : !aceso;
  digitalWrite(PINO_LED, nivel ? HIGH : LOW);
  Serial.printf("[LED ] %s\n", aceso ? "ACESA" : "APAGADA");
  enviarParaRaspberry();
}

// ============================================================================
//  PÁGINA HTML (PROGMEM) - Tudo integrado aqui
// ============================================================================
const char PAGINA[] PROGMEM = R"rawliteral(
<!DOCTYPE html><html lang="pt-BR"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Controle da Lâmpada</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    background: radial-gradient(circle at 50% 0%, #1e293b, #0b1120);
    color: #e2e8f0;
  }
  .card {
    width: min(90vw, 360px); padding: 32px 28px; border-radius: 20px;
    background: #111827; border: 1px solid #1f2937; text-align: center;
    box-shadow: 0 20px 50px rgba(0,0,0,.45);
  }
  h1 { font-size: 1.2rem; font-weight: 600; margin: 0 0 24px; color: #f1f5f9; }
  .bulb {
    width: 96px; height: 96px; border-radius: 50%; margin: 0 auto 16px;
    background: #1f2937; border: 2px solid #334155;
    transition: all .25s ease;
  }
  .bulb.on {
    background: radial-gradient(circle at 50% 40%, #fde68a, #f59e0b);
    border-color: #fbbf24;
    box-shadow: 0 0 40px 6px rgba(251,191,36,.55);
  }
  .timer {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 1.7rem; font-weight: 700; letter-spacing: .06em;
    color: #475569; margin-bottom: 6px; transition: color .25s ease;
  }
  .timer.on { color: #fbbf24; }
  .timer-label { font-size: .72rem; letter-spacing: .08em; text-transform: uppercase;
                 color: #475569; margin-bottom: 18px; }
  .status { font-size: 1.05rem; font-weight: 700; letter-spacing: .04em;
            margin-bottom: 22px; }
  .status.on  { color: #fbbf24; }
  .status.off { color: #64748b; }
  .btn {
    width: 100%; padding: 15px; border: none; border-radius: 12px;
    font-size: 1rem; font-weight: 600; cursor: pointer; color: #0b1120;
    background: #38bdf8; transition: transform .08s ease, opacity .2s;
  }
  .btn:active { transform: scale(.97); }
  .row { display: flex; gap: 10px; margin-top: 12px; }
  .row .btn { font-size: .9rem; padding: 12px; }
  .on-btn  { background: #fbbf24; }
  .off-btn { background: #475569; color: #e2e8f0; }
  .err { color: #f87171; font-size: .8rem; min-height: 1em; margin-top: 14px; }
</style></head><body>
<div class="card">
  <h1>Controle da Lâmpada</h1>
  <div id="bulb" class="bulb"></div>
  <div id="timer" class="timer">00:00:00</div>
  <div class="timer-label">tempo ligada</div>
  <div id="status" class="status off">—</div>
  <button class="btn" onclick="acao('toggle')">Alternar</button>
  <div class="row">
    <button class="btn on-btn"  onclick="acao('on')">Ligar</button>
    <button class="btn off-btn" onclick="acao('off')">Desligar</button>
  </div>
  <div id="err" class="err"></div>
</div>
<script>
  let aceso = false;
  let segundos = 0;

  function fmt(s){
    const h = String(Math.floor(s/3600)).padStart(2,'0');
    const m = String(Math.floor((s%3600)/60)).padStart(2,'0');
    const sec = String(s%60).padStart(2,'0');
    return h+':'+m+':'+sec;
  }
  function pintaTimer(){
    const t = document.getElementById('timer');
    t.textContent = fmt(segundos);
    t.className = 'timer ' + (aceso?'on':'off');
  }
  function render(estado, ligadoHa){
    aceso = estado;
    segundos = ligadoHa;
    document.getElementById('bulb').className = 'bulb ' + (aceso?'on':'off');
    var s = document.getElementById('status');
    s.className = 'status ' + (aceso?'on':'off');
    s.textContent = aceso ? 'ACESA' : 'APAGADA';
    pintaTimer();
  }
  async function req(rota){
    try {
      const r = await fetch('/'+rota, {cache:'no-store'});
      if(!r.ok) throw new Error(r.status);
      const j = await r.json();
      document.getElementById('err').textContent = '';
      render(j.aceso, j.ligadoHa);
    } catch(e){
      document.getElementById('err').textContent = 'Sem conexão com a placa';
    }
  }
  function acao(a){ req(a); }

  setInterval(()=>{ if(aceso){ segundos++; pintaTimer(); } }, 1000);

  req('state');
  setInterval(()=>req('state'), 3000);
</script></body></html>
)rawliteral";

// ============================================================================
//  HANDLERS HTTP
// ============================================================================
void enviarEstadoJson() {
  String json = String("{\"aceso\":") + (estadoLed ? "true" : "false")
              + ",\"ligadoHa\":" + segundosLigada() + "}";
  server.send(200, "application/json", json);
}

void handleRoot()   { server.send_P(200, "text/html", PAGINA); }
void handleOn()     { aplicarEstado(true);        enviarEstadoJson(); }
void handleOff()    { aplicarEstado(false);       enviarEstadoJson(); }
void handleToggle() { aplicarEstado(!estadoLed);  enviarEstadoJson(); }
void handleState()  { enviarEstadoJson(); }
void handleNotFound(){ server.send(404, "text/plain", "Nao encontrado"); }

// ============================================================================
//  WI-FI UnB (WPA2-Enterprise / PEAP / MSCHAPv2)
// ============================================================================
// Tenta uma rede da lista REDES[]. A identidade externa recebe o mesmo
// usuário (equivale a deixar "identidade anônima" em branco no manual) e
// nenhum certificado CA é passado, como o manual orienta.
bool tentarRede(int indice) {
  const RedeUnB& rede = REDES[indice];

  WiFi.disconnect(true);
  delay(200);
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);

  Serial.printf("[WiFi] Tentando \"%s\" como: %s\n", rede.ssid, rede.usuario.c_str());

  WiFi.begin(rede.ssid, WPA2_AUTH_PEAP,
             rede.usuario.c_str(),   // identidade externa
             rede.usuario.c_str(),   // usuário (MSCHAPv2)
             EAP_PASSWORD);

  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 30000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[WiFi] Conectado a \"%s\"!\n", rede.ssid);
    Serial.printf("[WiFi] IP: %s | http://%s.local\n", WiFi.localIP().toString().c_str(), HOSTNAME);
    return true;
  }
  Serial.printf("[WiFi] Falha em \"%s\".\n", rede.ssid);
  return false;
}

void conectarWiFi() {
  for (int i = 0; i < NUM_REDES; i++) {
    redeAtual = i;
    if (tentarRede(i)) return;
  }
  Serial.println("[WiFi] Nenhuma rede da UnB disponivel no momento.");
}

void garantirWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  unsigned long agora = millis();
  if (agora - ultimaTentativaWiFi >= INTERVALO_RECONEXAO_WIFI) {
    ultimaTentativaWiFi = agora;
    Serial.println("[WiFi] Conexao perdida. Tentando reconectar...");
    // alterna entre eduroam e UNB Wireless a cada tentativa
    if (!tentarRede(redeAtual)) {
      redeAtual = (redeAtual + 1) % NUM_REDES;
    }
  }
}

// ============================================================================
//  SETUP / LOOP
// ============================================================================
void setup() {
  Serial.begin(115200);
  delay(1500);

  Serial.println("\n=== Servidor Web - Lampada DC 12V (eduroam UnB) ===");

  pinMode(PINO_LED, OUTPUT);
  aplicarEstado(false);

  conectarWiFi();

  if (MDNS.begin(HOSTNAME)) {
    MDNS.addService("http", "tcp", 80);
    Serial.printf("[mDNS] http://%s.local ativo\n", HOSTNAME);
  }

  server.on("/",       handleRoot);
  server.on("/on",     handleOn);
  server.on("/off",    handleOff);
  server.on("/toggle", handleToggle);
  server.on("/state",  handleState);
  server.onNotFound(handleNotFound);

  server.begin();
  Serial.println("[HTTP] Servidor iniciado na porta 80");
}

void loop() {
  garantirWiFi();
  server.handleClient();
}