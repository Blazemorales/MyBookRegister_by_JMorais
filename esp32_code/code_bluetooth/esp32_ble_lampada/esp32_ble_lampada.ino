/*
 * ============================================================================
 *  Controle da Lâmpada via BLUETOOTH (BLE)  |  ESP32-S3 ou ESP32 WROOM-32
 * ============================================================================
 *
 *  Usa BLE com o serviço Nordic UART (NUS) — um "Serial via Bluetooth".
 *  Você digita comandos no celular e a ESP32 responde com o estado.
 *
 *  POR QUE BLE E NÃO BLUETOOTH CLÁSSICO?
 *   - A ESP32-S3 NÃO tem Bluetooth Clássico (BluetoothSerial.h não compila).
 *     Ela só tem BLE. Este sketch usa BLE, então funciona na S3 E na WROOM-32.
 *
 *  COMO TESTAR NO CELULAR (Android):
 *   - App "Serial Bluetooth Terminal" (Kai Morich):
 *       Devices → aba "Bluetooth LE" → conectar em "Lampada-BLE" → digitar
 *       ON / OFF / TOGGLE.
 *   - Ou "nRF Connect": conectar, achar o serviço Nordic UART, escrever na
 *     característica RX (Write) e habilitar Notify na TX.
 *
 *  Comandos aceitos (iguais aos das versões MQTT/Web):
 *   ON / 1 / LIGAR   ·   OFF / 0 / DESLIGAR   ·   TOGGLE / ALTERNAR
 *   STATUS  → responde o estado atual
 *
 *  Hardware: GPIO4 → S do módulo relé (5V → +, GND → −). Lâmpada nos contatos.
 *  Biblioteca BLE: já vem no core da ESP32 (não precisa instalar nada).
 * ============================================================================
 */

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// ============================================================================
//  CONFIGURAÇÃO
// ============================================================================
const char* NOME_BLE = "Lampada-BLE";   // nome que aparece no celular

const uint8_t PINO_RELE      = 12;       // GPIO -> S do módulo relé
const bool    RELE_ATIVO_ALTO = true;   // true p/ módulo ativo-alto (KY-019);
                                        // troque p/ false se acionar invertido

// UUIDs do Nordic UART Service (padrão de mercado — os apps reconhecem)
#define UUID_SERVICO "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define UUID_RX      "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  // celular ESCREVE aqui
#define UUID_TX      "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  // ESP32 NOTIFICA aqui

// ============================================================================
//  ESTADO
// ============================================================================
BLEServer*         servidor  = nullptr;
BLECharacteristic* charTX    = nullptr;
bool  conectado   = false;
bool  estadoLed   = false;   // false = lâmpada apagada

// ============================================================================
//  HARDWARE + RESPOSTA
// ============================================================================
void aplicarEstado(bool aceso) {
  estadoLed = aceso;
  bool nivel = RELE_ATIVO_ALTO ? aceso : !aceso;
  digitalWrite(PINO_RELE, nivel ? HIGH : LOW);
  Serial.printf("[RELE] Lampada %s\n", aceso ? "ACESA" : "APAGADA");
}

// Envia texto pro celular (notify na característica TX)
void responder(const String& msg) {
  Serial.printf("[BLE ] -> %s\n", msg.c_str());
  if (conectado && charTX) {
    charTX->setValue((msg + "\n").c_str());
    charTX->notify();
  }
}

void interpretarComando(String msg) {
  msg.trim();
  msg.toUpperCase();
  if (msg == "ON" || msg == "1" || msg == "LIGAR") {
    aplicarEstado(true);   responder("LAMPADA: ACESA");
  } else if (msg == "OFF" || msg == "0" || msg == "DESLIGAR") {
    aplicarEstado(false);  responder("LAMPADA: APAGADA");
  } else if (msg == "TOGGLE" || msg == "ALTERNAR") {
    aplicarEstado(!estadoLed);
    responder(String("LAMPADA: ") + (estadoLed ? "ACESA" : "APAGADA"));
  } else if (msg == "STATUS" || msg == "ESTADO") {
    responder(String("LAMPADA: ") + (estadoLed ? "ACESA" : "APAGADA"));
  } else if (msg.length() > 0) {
    responder("Comando invalido. Use: ON / OFF / TOGGLE / STATUS");
  }
}

// ============================================================================
//  CALLBACKS BLE
// ============================================================================
class CBServidor : public BLEServerCallbacks {
  void onConnect(BLEServer*) override {
    conectado = true;
    Serial.println("[BLE ] Celular conectado");
  }
  void onDisconnect(BLEServer* s) override {
    conectado = false;
    Serial.println("[BLE ] Celular desconectado; voltando a anunciar...");
    s->getAdvertising()->start();   // volta a aparecer na busca do celular
  }
};

class CBRecebe : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    String valor = String(c->getValue().c_str());
    Serial.printf("[BLE ] <- %s\n", valor.c_str());
    interpretarComando(valor);
  }
};

// ============================================================================
//  SETUP / LOOP
// ============================================================================
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== Lampada via Bluetooth (BLE / Nordic UART) ===");

  pinMode(PINO_RELE, OUTPUT);
  aplicarEstado(false);   // começa apagada

  // ---- Monta o servidor BLE ----
  BLEDevice::init(NOME_BLE);
  servidor = BLEDevice::createServer();
  servidor->setCallbacks(new CBServidor());

  BLEService* servico = servidor->createService(UUID_SERVICO);

  // TX: ESP32 -> celular (notify)
  charTX = servico->createCharacteristic(
      UUID_TX, BLECharacteristic::PROPERTY_NOTIFY);
  charTX->addDescriptor(new BLE2902());

  // RX: celular -> ESP32 (write)
  BLECharacteristic* charRX = servico->createCharacteristic(
      UUID_RX,
      BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  charRX->setCallbacks(new CBRecebe());

  servico->start();

  // Anuncia o serviço (necessário p/ o app filtrar por UART)
  BLEAdvertising* adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(UUID_SERVICO);
  adv->setScanResponse(true);
  adv->start();

  Serial.printf("[BLE ] Anunciando como '%s'. Conecte pelo app e digite ON/OFF.\n",
                NOME_BLE);
}

void loop() {
  // Tudo é orientado a eventos (callbacks); nada a fazer aqui.
  delay(50);
}
