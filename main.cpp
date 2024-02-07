#include <Arduino.h>
#include <task.h>
#include <queue.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <PubSubClient.h>

// constants
#define MQTT_BROKER       "broker.hivemq.com"
#define MQTT_PORT         1883
#define MQTT_SOUND_TOPIC  "taist/aiot/dev" //pub

#define MQTT_HB_TOPIC     "taist/aiot/heartbeat/dev" //pub
#define MQTT_CMD_TOPIC    "taist/aiot/command/dev" //sub

#define WIFI_SSID         "xxxx"
#define WIFI_PASSWORD     "xxxx"

// global variables
WiFiClient wifi_client;
PubSubClient mqtt_client(wifi_client);

// queue handle
QueueHandle_t evt_queue;
void on_cmd_received(char* topic, byte* payload, unsigned int length) {
  // ignored
}


// task to send to MQTT 
void comm_task(void *pvParameter) {
  // initialize serial and network
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  mqtt_client.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt_client.setCallback(on_cmd_received);
  mqtt_client.connect("taist_MQTT_test");

    // communicate with MQTT
  Serial.printf("connected");
  if (mqtt_client.connected()) {
    mqtt_client.publish(MQTT_HB_TOPIC, "test");
  }
  
}

void setup() {
  // prepare WiFi and MQTT


  // initialize RTOS task
  evt_queue = xQueueCreate(10, sizeof(float));

  // create tasks

  xTaskCreate(
    comm_task,    // task function
    "comm_task",  // name of task
    4096,         // stack size of task
    NULL,         // parameter of the task
    2,            // priority of the task
    NULL          // task handle to keep track of created task
  );
}

void loop() {
  // execute MQTT loop
  if(mqtt_client.connected()){
    mqtt_client.loop();
  }
  delay(1000);
}
