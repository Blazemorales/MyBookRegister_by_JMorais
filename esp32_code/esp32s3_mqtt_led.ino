/*
 * esp32s3_mqtt_led.ino
 * ESP32-S3-N16R8 — controle de lâmpada DC 12V via MQTT
 * Circuito: GPIO4 → R220Ω → PC817 → gate IRF540N → lâmpada (low-side)
 *
 * Biblioteca: PubSubClient  https://github.com/knolleary/pubsubclient
 * Board: "ESP32S3 Dev Module"
 * PSRAM: OPI PSRAM | Flash: 16MB | USB CDC On Boot: Enabled | Upload: 921600
 */

#include <WiFi.h>
#include <PubSubClient.h>

// ─── Configuração ──────────────────────────────────────────────────────────
const char* WIFI_SSID     = "SEU_SSID";
const char* WIFI_PASSWORD = "SUA_SENHA";
const char* MQTT_BROKER   = "192.168.0.42";   // ← IP da Raspberry Pi (hostname -I)
const int   MQTT_PORT     = 1883;

// GPIO conectado ao LED do PC817 (via R 220Ω)
// NÃO usar GPIOs 33-37 (reservados pelo OPI PSRAM)
const uint8_t PINO_LED = 4;

// true = GPIO HIGH acende a lâmpada (active-high, como neste circuito)
// false = GPIO LOW acende (active-low, para relés com lógica invertida)
const bool LED_ATIVO_ALTO = true;

// ─── Tópicos MQTT ──────────────────────────────────────────────────────────
const char* TOPICO_CMD   = "jmorais/esp32s3/led/comando";
const char* TOPICO_ESTADO = "jmorais/esp32s3/led/estado";
const char* TOPICO_LWT   = "jmorais/esp32s3/led/disponibilidade";

// ─── Globais ───────────────────────────────────────────────────────────────
WiFiClient   espClient;
PubSubClient mqtt(espClient);

bool estadoLed = false;

unsigned long ultimoTentativaMQTT = 0;
const unsigned long INTERVALO_RECONEXAO = 5000;

// ─── Helpers ───────────────────────────────────────────────────────────────
void aplicarEstado(bool ligar) {
    estadoLed = ligar;
    digitalWrite(PINO_LED, LED_ATIVO_ALTO ? ligar : !ligar);
    const char* msg = ligar ? "ON" : "OFF";
    // retain=true: qualquer cliente que assinar recebe o estado atual imediatamente
    mqtt.publish(TOPICO_ESTADO, msg, /*retain=*/true);
    Serial.printf("[LED] %s\n", msg);
}

void callbackMQTT(char* topico, byte* payload, unsigned int len) {
    String cmd;
    cmd.reserve(len);
    for (unsigned int i = 0; i < len; i++) cmd += (char)payload[i];
    cmd.trim();

    Serial.printf("[MQTT] %s → %s\n", topico, cmd.c_str());

    if (cmd == "ON"  || cmd == "1" || cmd == "LIGAR")   aplicarEstado(true);
    else if (cmd == "OFF" || cmd == "0" || cmd == "DESLIGAR") aplicarEstado(false);
    else if (cmd == "TOGGLE") aplicarEstado(!estadoLed);
    else Serial.printf("[MQTT] Comando desconhecido: %s\n", cmd.c_str());
}

String clientID() {
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char buf[20];
    snprintf(buf, sizeof(buf), "esp32s3-%02X%02X%02X", mac[3], mac[4], mac[5]);
    return String(buf);
}

// ─── Wi-Fi ─────────────────────────────────────────────────────────────────
void conectarWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;
    Serial.printf("[WiFi] Conectando a %s", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print('.');
    }
    Serial.printf("\n[WiFi] Conectado — IP: %s\n", WiFi.localIP().toString().c_str());
}

// ─── MQTT ──────────────────────────────────────────────────────────────────
void conectarMQTT() {
    String id = clientID();
    Serial.printf("[MQTT] Conectando como %s …\n", id.c_str());

    // LWT: broker publica "offline" automaticamente se a ESP32 cair
    bool ok = mqtt.connect(
        id.c_str(),
        /*user=*/nullptr, /*pass=*/nullptr,
        TOPICO_LWT, /*qos=*/1, /*retain=*/true, "offline"
    );

    if (ok) {
        Serial.println("[MQTT] Conectado");
        mqtt.publish(TOPICO_LWT, "online", /*retain=*/true);
        mqtt.subscribe(TOPICO_CMD);
        // Publica o estado atual ao (re)conectar para sincronizar clientes novos
        aplicarEstado(estadoLed);
    } else {
        Serial.printf("[MQTT] Falha rc=%d — tentando em %lus\n",
                      mqtt.state(), INTERVALO_RECONEXAO / 1000);
    }
}

// ─── Setup / Loop ──────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("\n[Boot] ESP32-S3 MQTT LED v1.0");

    pinMode(PINO_LED, OUTPUT);
    aplicarEstado(false);   // garante lâmpada desligada ao boot (sem MQTT ainda)

    conectarWiFi();
    mqtt.setServer(MQTT_BROKER, MQTT_PORT);
    mqtt.setCallback(callbackMQTT);
    mqtt.setKeepAlive(15);
    conectarMQTT();
}

void loop() {
    // Reconexão Wi-Fi não-bloqueante
    if (WiFi.status() != WL_CONNECTED) {
        conectarWiFi();
    }

    // Reconexão MQTT não-bloqueante
    if (!mqtt.connected()) {
        unsigned long agora = millis();
        if (agora - ultimoTentativaMQTT >= INTERVALO_RECONEXAO) {
            ultimoTentativaMQTT = agora;
            conectarMQTT();
        }
    } else {
        mqtt.loop();
    }
}
