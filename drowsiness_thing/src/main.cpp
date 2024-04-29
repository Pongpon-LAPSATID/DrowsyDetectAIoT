#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <PubSubClient.h>
#include <task.h>
#include <queue.h>
#include "hw_camera.h"
#include <drowsiness_inferencing.h>
#include "edge-impulse-sdk/dsp/image/image.hpp"
#include <ArduinoJson.h>

// Constants
const char *ssid = "XXX"; // Enter your Wi-Fi name
const char *password = "XXX";  // Enter Wi-Fi password

#define TAG     "main"

// MQTT Broker
const char *mqtt_broker = "broker.hivemq.com";
const char *topic = "aiot/drowsiness";
const char *mqtt_username = "XXX";
const int mqtt_port = 1883;

WiFiClient espClient;
PubSubClient client(espClient);
StaticJsonDocument<200> json_doc;

#define EI_CAMERA_RAW_FRAME_BUFFER_COLS           240
#define EI_CAMERA_RAW_FRAME_BUFFER_ROWS           240
#define EI_CAMERA_FRAME_BYTE_SIZE                 3
#define BMP_BUF_SIZE                             (EI_CAMERA_RAW_FRAME_BUFFER_COLS * EI_CAMERA_RAW_FRAME_BUFFER_ROWS * EI_CAMERA_FRAME_BYTE_SIZE)

// static variables
static uint8_t *bmp_buf;

// Function prototypes
void callback(char *topic, byte *payload, unsigned int length);
void publishMessage(const char *msg);
void ei_prepare_feature(uint8_t *img_buf, signal_t *signal);
int ei_get_feature_callback(size_t offset, size_t length, float *out_ptr);
void ei_use_result(ei_impulse_result_t result);
void captureAndProcessImage(void *parameter);

void setup() {
    // Set software serial baud to 115200;
    Serial.begin(115200);
    // Connecting to a WiFi network
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.println("Connecting to WiFi..");
    }
    Serial.println("Connected to the Wi-Fi network");
    // Allocate memory for the camera snapshot buffer
    bmp_buf = (uint8_t *)malloc(BMP_BUF_SIZE);
    if (!bmp_buf) {
        Serial.println("Failed to allocate memory for bmp_buf");
        while (1)
            ; // Loop indefinitely if memory allocation fails
    }
    //connecting to a mqtt broker
    client.setServer(mqtt_broker, mqtt_port);
    client.setCallback(callback); // Now callback is declared or prototyped before this line
    while (!client.connected()) {
        String client_id = "esp32-client-";
        client_id += String(WiFi.macAddress());
        Serial.printf("The client %s connects to the public MQTT broker\n", client_id.c_str());
        if (client.connect(mqtt_username)) {
            Serial.println("Public MQTT broker connected");
        } else {
            Serial.print("failed with state ");
            Serial.print(client.state());
            delay(2000);
        }
    }

    hw_camera_init();

    // Start a timer to capture and process image every 1 second
    xTaskCreatePinnedToCore(
        captureAndProcessImage,   /* Function to implement the task */
        "ImageCaptureTask",       /* Name of the task */
        10000,                    /* Stack size in words */
        NULL,                     /* Task input parameter (cast to void*) */
        1,                        /* Priority of the task */
        NULL,                     /* Task handle */
        0                         /* Core where the task should run */
    );
}

void loop() {
    // Nothing to do in the main loop since image capture is handled by a timer
    delay(1000); // Delay to avoid heavy CPU load
}

void captureAndProcessImage(void *parameter) {
    while (true) {
        uint32_t Tstart, elapsed_time;
        uint32_t width, height;

        Tstart = millis();
        // get raw data
        Serial.println("Taking snapshot...");
        hw_camera_raw_snapshot(bmp_buf, &width, &height);
        elapsed_time = millis() - Tstart;
        Serial.printf("Snapshot taken (%d) width: %d, height: %d\n", elapsed_time, width, height);
        // prepare feature
        Tstart = millis();
        ei::signal_t signal;
        ei_prepare_feature(bmp_buf, &signal);
        elapsed_time = millis() - Tstart;
        Serial.printf("Feature taken (%d)\n", elapsed_time);
        // run classifier
        Tstart = millis();
        ei_impulse_result_t result = {0};
        bool debug_nn = false;
        run_classifier(&signal, &result, debug_nn);
        elapsed_time = millis() - Tstart;
        Serial.printf("Classification done (%d)\n", elapsed_time);
        // use result
        ei_use_result(result);

        // Wait for 1 second before capturing the next image
        delay(1000);
    }
}

// Print memory information
void print_memory() {
    Serial.printf("Total heap: %u\n", ESP.getHeapSize());
    Serial.printf("Free heap: %u\n", ESP.getFreeHeap());
    Serial.printf("Total PSRAM: %u\n", ESP.getPsramSize());
    Serial.printf("Free PSRAM: %d\n", ESP.getFreePsram());
}

// prepare feature
void ei_prepare_feature(uint8_t *img_buf, signal_t *signal) {
    signal->total_length = EI_CLASSIFIER_INPUT_WIDTH * EI_CLASSIFIER_INPUT_HEIGHT;
    signal->get_data = &ei_get_feature_callback;
    if ((EI_CAMERA_RAW_FRAME_BUFFER_ROWS != EI_CLASSIFIER_INPUT_WIDTH) || (EI_CAMERA_RAW_FRAME_BUFFER_COLS != EI_CLASSIFIER_INPUT_HEIGHT)) {
        ei::image::processing::crop_and_interpolate_rgb888(
            img_buf,
            EI_CAMERA_RAW_FRAME_BUFFER_COLS,
            EI_CAMERA_RAW_FRAME_BUFFER_ROWS,
            img_buf,
            EI_CLASSIFIER_INPUT_WIDTH,
            EI_CLASSIFIER_INPUT_HEIGHT);
    }
}

// get feature callback
int ei_get_feature_callback(size_t offset, size_t length, float *out_ptr) {
    size_t pixel_ix = offset * 3;
    size_t pixels_left = length;
    size_t out_ptr_ix = 0;

    while (pixels_left != 0) {
        out_ptr[out_ptr_ix] = (bmp_buf[pixel_ix] << 16) + (bmp_buf[pixel_ix + 1] << 8) + bmp_buf[pixel_ix + 2];

        // go to the next pixel
        out_ptr_ix++;
        pixel_ix += 3;
        pixels_left--;
    }
    return 0;
}

// use result from classifier
void ei_use_result(ei_impulse_result_t result) {
    bool bb_found = result.bounding_boxes[0].value > 0;
    int close_count = 0; // Counter for "Close" labels
    for (size_t ix = 0; ix < result.bounding_boxes_count; ix++) {
        auto bb = result.bounding_boxes[ix];
        if (bb.value == 0) {
            continue;
        }
        Serial.printf("%s (%f) ", bb.label, bb.value);
        if (bb.label == "Open") {
            json_doc.clear();
            json_doc["eye_status"] = "1";
            json_doc["alarm_status"] = "0";
            json_doc["timestamp"] = millis();
            // Publish the bounding box label
            publishMessage(json_doc.as<String>().c_str());
            close_count = 0; // Reset close count if Open label detected
        }
        else if (bb.label == "Close") {
            close_count++; // Increment close count for "Close" labels
            if (close_count >= 3) {
                Serial.println("Alarm on");
                json_doc.clear();
                json_doc["eye_status"] = "0";
                json_doc["alarm_status"] = "1"; // Set alarm status to "1"
                json_doc["timestamp"] = millis();
                // Publish the alarm status
                publishMessage(json_doc.as<String>().c_str());
            } else {
                json_doc.clear();
                json_doc["eye_status"] = "0";
                json_doc["alarm_status"] = "0";
                json_doc["timestamp"] = millis();
                // Publish the bounding box label
                publishMessage(json_doc.as<String>().c_str());
            }
        }
    }
    if (!bb_found) {
        Serial.println("No objects found");
    }
}



// MQTT callback
void callback(char *topic, byte *payload, unsigned int length) {
    Serial.print("Message arrived in topic: ");
    Serial.println(topic);
    Serial.print("Message:");
    for (int i = 0; i < length; i++) {
        Serial.print((char)payload[i]);
    }
    Serial.println();
    Serial.println("-----------------------");
}

// Publish message to MQTT broker
void publishMessage(const char *msg) {
    client.publish(topic, msg);
}
