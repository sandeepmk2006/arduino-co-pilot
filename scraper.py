"""
Arduino Documentation Scraper
Scrapes Arduino Language Reference, board pinouts, and library docs.
Also includes a built-in knowledge base for offline use.
"""
import requests
from bs4 import BeautifulSoup
import json
import os
from pathlib import Path
import time
import re

class ArduinoDocsScraper:
    def __init__(self, output_dir="docs_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.base_url = "https://docs.arduino.cc"
        self.docs = []

    # ── Built-in Knowledge Base (works offline) ────────────────────────
    def _builtin_language_reference(self):
        """Core Arduino language reference snippets."""
        return [
            # Digital I/O
            {"title": "pinMode()", "category": "Digital I/O", "content": "pinMode(pin, mode) - Configures the specified pin to behave either as an input or an output. mode: INPUT, OUTPUT, or INPUT_PULLUP. Example: pinMode(13, OUTPUT); sets pin 13 as output."},
            {"title": "digitalWrite()", "category": "Digital I/O", "content": "digitalWrite(pin, value) - Write HIGH or LOW to a digital pin. If the pin is configured as OUTPUT, sets voltage to 5V (HIGH) or 0V (LOW). Example: digitalWrite(13, HIGH); turns on LED on pin 13."},
            {"title": "digitalRead()", "category": "Digital I/O", "content": "digitalRead(pin) - Reads the value from a specified digital pin, either HIGH or LOW. Returns int. Example: int val = digitalRead(2); reads pin 2 state."},

            # Analog I/O
            {"title": "analogRead()", "category": "Analog I/O", "content": "analogRead(pin) - Reads the value from the specified analog pin. Returns int 0-1023 (10-bit ADC). Arduino Uno analog pins: A0-A5. Takes about 100 microseconds. Example: int sensorValue = analogRead(A0);"},
            {"title": "analogWrite()", "category": "Analog I/O", "content": "analogWrite(pin, value) - Writes an analog value (PWM wave) to a pin. value: 0-255 duty cycle. PWM pins on Uno: 3, 5, 6, 9, 10, 11. Frequency: ~490 Hz (pins 5,6: ~980 Hz). Example: analogWrite(9, 128); // 50% duty cycle."},
            {"title": "analogReference()", "category": "Analog I/O", "content": "analogReference(type) - Configures the reference voltage for analog input. Types: DEFAULT (5V on Uno), INTERNAL (1.1V on Uno), EXTERNAL (voltage on AREF pin). Example: analogReference(INTERNAL);"},

            # Time
            {"title": "millis()", "category": "Time", "content": "millis() - Returns the number of milliseconds since the Arduino began running. Returns unsigned long. Overflows after ~50 days. Use for non-blocking delays. Example: unsigned long currentTime = millis();"},
            {"title": "micros()", "category": "Time", "content": "micros() - Returns microseconds since program started. Resolution of 4 microseconds on 16 MHz boards. Overflows after ~70 minutes. Example: unsigned long t = micros();"},
            {"title": "delay()", "category": "Time", "content": "delay(ms) - Pauses the program for ms milliseconds. 1000 ms = 1 second. Blocking function - no other code runs during delay. Example: delay(1000); // wait 1 second."},
            {"title": "delayMicroseconds()", "category": "Time", "content": "delayMicroseconds(us) - Pauses program for us microseconds. Accurate for values 3 and above. Max recommended: 16383. Example: delayMicroseconds(100);"},

            # Serial
            {"title": "Serial.begin()", "category": "Serial", "content": "Serial.begin(speed) - Sets the data rate in bits per second (baud). Common rates: 9600, 115200. Must be called in setup(). Example: Serial.begin(9600);"},
            {"title": "Serial.print()", "category": "Serial", "content": "Serial.print(val) - Prints data to the serial port as human-readable ASCII text. Can print strings, ints, floats. Serial.println() adds newline. Example: Serial.println(\"Hello\");"},
            {"title": "Serial.read()", "category": "Serial", "content": "Serial.read() - Reads incoming serial data. Returns first byte of incoming serial data or -1 if none. Use Serial.available() to check first. Example: if(Serial.available()) { char c = Serial.read(); }"},
            {"title": "Serial.available()", "category": "Serial", "content": "Serial.available() - Returns the number of bytes available for reading from the serial port. Returns int. Example: if (Serial.available() > 0) { int inByte = Serial.read(); }"},

            # Math
            {"title": "map()", "category": "Math", "content": "map(value, fromLow, fromHigh, toLow, toHigh) - Re-maps a number from one range to another. Does not constrain values. Example: int val = map(analogRead(A0), 0, 1023, 0, 255);"},
            {"title": "constrain()", "category": "Math", "content": "constrain(x, a, b) - Constrains a number to be within a range. Returns x if between a and b, a if x < a, b if x > b. Example: int val = constrain(sensorValue, 0, 255);"},
            {"title": "min() / max()", "category": "Math", "content": "min(x, y) - Returns the smaller of two numbers. max(x, y) - Returns the larger. Avoid using with side-effect expressions. Example: int smallest = min(a, b);"},
            {"title": "abs()", "category": "Math", "content": "abs(x) - Computes the absolute value. Avoid using with side-effect expressions due to macro implementation. Example: int distance = abs(target - current);"},
            {"title": "pow()", "category": "Math", "content": "pow(base, exponent) - Calculates the value of a number raised to a power. Returns double. Example: double val = pow(2, 8); // 256"},
            {"title": "sqrt()", "category": "Math", "content": "sqrt(x) - Calculates the square root. Returns double. Example: double root = sqrt(144); // 12"},
            {"title": "random()", "category": "Math", "content": "random(max) or random(min, max) - Generates pseudo-random numbers. Use randomSeed() for true randomness. Example: long r = random(0, 100);"},

            # Interrupts
            {"title": "attachInterrupt()", "category": "Interrupts", "content": "attachInterrupt(digitalPinToInterrupt(pin), ISR, mode) - Sets a function (ISR) to call when an external interrupt occurs. Modes: LOW, CHANGE, RISING, FALLING. Uno interrupt pins: 2, 3. ISR should be short, no delay(), no Serial. Use volatile for shared variables. Example: attachInterrupt(digitalPinToInterrupt(2), myISR, RISING);"},
            {"title": "detachInterrupt()", "category": "Interrupts", "content": "detachInterrupt(digitalPinToInterrupt(pin)) - Turns off the interrupt on the specified pin. Example: detachInterrupt(digitalPinToInterrupt(2));"},
            {"title": "interrupts() / noInterrupts()", "category": "Interrupts", "content": "interrupts() - Re-enables interrupts after noInterrupts() disabled them. noInterrupts() - Disables interrupts. Use in critical sections. Example: noInterrupts(); criticalCode(); interrupts();"},

            # Communication
            {"title": "Wire (I2C)", "category": "Communication", "content": "#include <Wire.h> - I2C communication library. Wire.begin() starts as master, Wire.begin(address) as slave. Wire.beginTransmission(address), Wire.write(data), Wire.endTransmission(). Wire.requestFrom(address, count), Wire.read(). SDA: A4, SCL: A5 on Uno. Example: Wire.begin(); Wire.beginTransmission(0x27); Wire.write(value); Wire.endTransmission();"},
            {"title": "SPI", "category": "Communication", "content": "#include <SPI.h> - SPI communication library. Pins on Uno: MOSI=11, MISO=12, SCK=13, SS=10. SPI.begin(), SPI.transfer(val). Use digitalWrite(SS, LOW) to select device. Example: SPI.begin(); digitalWrite(SS, LOW); SPI.transfer(0x42); digitalWrite(SS, HIGH);"},
            {"title": "SoftwareSerial", "category": "Communication", "content": "#include <SoftwareSerial.h> - Allows serial on other digital pins. SoftwareSerial mySerial(rxPin, txPin). Not all pins support RX. Max one instance active at a time. Example: SoftwareSerial bt(10, 11); bt.begin(9600);"},

            # Common Libraries
            {"title": "Servo Library", "category": "Libraries", "content": "#include <Servo.h> - Controls servo motors. Servo myservo; myservo.attach(pin). myservo.write(angle) for 0-180 degrees. myservo.writeMicroseconds(us) for precise control (1000-2000us). Can use any digital pin. Max 12 servos on Uno. Disables PWM on pins 9,10. Example: Servo myservo; myservo.attach(9); myservo.write(90);"},
            {"title": "LiquidCrystal", "category": "Libraries", "content": "#include <LiquidCrystal.h> - Controls LCD displays. LiquidCrystal lcd(rs, en, d4, d5, d6, d7). lcd.begin(cols, rows). lcd.print(). lcd.setCursor(col, row). lcd.clear(). Example: LiquidCrystal lcd(12, 11, 5, 4, 3, 2); lcd.begin(16, 2); lcd.print(\"Hello\");"},
            {"title": "Stepper Library", "category": "Libraries", "content": "#include <Stepper.h> - Controls stepper motors. Stepper myStepper(stepsPerRev, pin1, pin2, pin3, pin4). myStepper.setSpeed(rpm). myStepper.step(steps). Example: Stepper motor(200, 8, 9, 10, 11); motor.setSpeed(60); motor.step(200);"},
            {"title": "EEPROM", "category": "Libraries", "content": "#include <EEPROM.h> - Read/write to permanent storage. EEPROM.read(address), EEPROM.write(address, value), EEPROM.update(address, value). Uno: 1024 bytes. 100,000 write cycles. Example: EEPROM.write(0, 42); int val = EEPROM.read(0);"},
            {"title": "WiFiNINA", "category": "Libraries", "content": "#include <WiFiNINA.h> - Wi-Fi for Arduino MKR, Nano 33 IoT. WiFi.begin(ssid, pass). WiFi.status(). WiFiClient/WiFiServer for TCP. WiFiSSLClient for HTTPS. Example: WiFi.begin(\"myNetwork\", \"myPassword\"); while(WiFi.status() != WL_CONNECTED) delay(500);"},
            {"title": "ArduinoBLE", "category": "Libraries", "content": "#include <ArduinoBLE.h> - BLE for Nano 33 BLE, MKR WiFi 1010. BLE.begin(). BLEService/BLECharacteristic to define services. BLE.advertise(). Example: BLEService ledService(\"19B10000-...\"); BLEByteCharacteristic ledChar(\"19B10001-...\", BLERead | BLEWrite);"},

            # Data Types
            {"title": "Data Types", "category": "Language", "content": "Arduino data types: boolean (true/false, 1 byte), byte (0-255, 1 byte), char (-128 to 127, 1 byte), unsigned char, int (-32768 to 32767, 2 bytes on Uno), unsigned int (0 to 65535), long (4 bytes), unsigned long, float (4 bytes, 6-7 decimal digits), double (same as float on Uno), String (object), char[] (C-string)."},
            {"title": "String Object", "category": "Language", "content": "String class for text manipulation. String str = \"Hello\"; str.length(); str.charAt(n); str.substring(from, to); str.indexOf(\"find\"); str.toUpperCase(); str.toInt(); str += \" World\"; str.equals(str2); Warning: dynamic memory allocation can cause heap fragmentation. Prefer char arrays for memory-constrained applications."},

            # Control Structures
            {"title": "Control Structures", "category": "Language", "content": "if/else, for, while, do...while, switch/case, break, continue, return, goto. for(int i=0; i<10; i++) {...}. while(condition) {...}. switch(var) { case 1: ...; break; default: ...; }"},

            # Advanced
            {"title": "volatile keyword", "category": "Advanced", "content": "volatile - Tells compiler variable may change unexpectedly (in ISR). Always use for variables shared between ISR and main code. Example: volatile int encoderCount = 0;"},
            {"title": "Low Power Sleep", "category": "Advanced", "content": "Power saving with sleep modes. #include <avr/sleep.h> #include <avr/power.h>. set_sleep_mode(SLEEP_MODE_PWR_DOWN); sleep_enable(); sleep_mode(); sleep_disable(); Use watchdog timer or external interrupt to wake. Reduces Uno from ~45mA to ~0.36uA."},
            {"title": "Watchdog Timer", "category": "Advanced", "content": "#include <avr/wdt.h> - Hardware watchdog timer. wdt_enable(WDTO_2S) enables 2-second watchdog. Must call wdt_reset() within timeout or board resets. Useful for crash recovery. Values: WDTO_15MS to WDTO_8S."},
            {"title": "Direct Port Manipulation", "category": "Advanced", "content": "Direct register access for fast I/O. DDRB (direction), PORTB (output), PINB (input). Uno: Port B = pins 8-13, Port D = pins 0-7, Port C = A0-A5. DDRB |= (1 << PB5); // pin 13 output. PORTB |= (1 << PB5); // pin 13 HIGH. ~62.5ns vs ~5us for digitalWrite."},
        ]

    def _builtin_board_pinouts(self):
        """Board pinout data."""
        return [
            {"title": "Arduino Uno R3 Pinout", "category": "Board Pinout", "content": """Arduino Uno R3:
- Microcontroller: ATmega328P, 16 MHz, 5V logic
- Digital I/O Pins: 14 (D0-D13), of which 6 provide PWM output
- PWM Pins: 3, 5, 6, 9, 10, 11 (marked with ~)
- Analog Input Pins: 6 (A0-A5), 10-bit ADC (0-1023)
- DC Current per I/O Pin: 20 mA (absolute max 40 mA)
- Flash Memory: 32 KB (0.5 KB used by bootloader)
- SRAM: 2 KB
- EEPROM: 1 KB
- I2C: SDA (A4), SCL (A5)
- SPI: MOSI (11), MISO (12), SCK (13), SS (10)
- Serial: TX (1), RX (0)
- External Interrupts: Pin 2 (INT0), Pin 3 (INT1)
- LED_BUILTIN: Pin 13
- Operating Voltage: 5V, Input Voltage: 7-12V (limit 6-20V)
- USB: Type-B for programming and serial communication"""},

            {"title": "Arduino Nano Pinout", "category": "Board Pinout", "content": """Arduino Nano:
- Microcontroller: ATmega328P, 16 MHz, 5V logic
- Digital I/O Pins: 14 (D0-D13), 6 PWM (3, 5, 6, 9, 10, 11)
- Analog Input Pins: 8 (A0-A7), 10-bit ADC
- Flash: 32 KB, SRAM: 2 KB, EEPROM: 1 KB
- Form factor: Mini-B USB, breadboard-friendly
- Same pinout as Uno but smaller form factor
- Extra analog pins: A6, A7 (analog input only, no digital)
- I2C: SDA (A4), SCL (A5), SPI: same as Uno"""},

            {"title": "Arduino Mega 2560 Pinout", "category": "Board Pinout", "content": """Arduino Mega 2560:
- Microcontroller: ATmega2560, 16 MHz, 5V logic
- Digital I/O Pins: 54 (D0-D53), of which 15 provide PWM
- PWM Pins: 2-13, 44-46
- Analog Input Pins: 16 (A0-A15), 10-bit ADC
- Flash: 256 KB, SRAM: 8 KB, EEPROM: 4 KB
- Serial Ports: 4 (Serial, Serial1, Serial2, Serial3)
- I2C: SDA (20), SCL (21)
- SPI: MOSI (51), MISO (50), SCK (52), SS (53)
- External Interrupts: 2, 3, 18, 19, 20, 21
- DC Current per Pin: 20 mA"""},

            {"title": "Arduino Nano 33 IoT Pinout", "category": "Board Pinout", "content": """Arduino Nano 33 IoT:
- Microcontroller: SAMD21 Cortex-M0+ 48MHz, 3.3V logic
- Connectivity: Wi-Fi (u-blox NINA-W102), Bluetooth 4.2/BLE
- IMU: LSM6DS3 (accelerometer + gyroscope)
- Digital I/O: 14, Analog Input: 8 (A0-A7, 12-bit ADC)
- PWM: all digital pins, DAC: A0
- Flash: 256 KB, SRAM: 32 KB
- I2C: SDA (A4), SCL (A5)
- IMPORTANT: 3.3V logic - do NOT connect 5V signals directly
- Libraries: WiFiNINA, ArduinoBLE, Arduino_LSM6DS3"""},

            {"title": "Arduino Uno R4 WiFi Pinout", "category": "Board Pinout", "content": """Arduino Uno R4 WiFi:
- Microcontroller: Renesas RA4M1 (Arm Cortex-M4, 48 MHz)
- Wi-Fi/BLE: ESP32-S3 module
- Digital I/O: 14 (D0-D13), PWM on all digital pins
- Analog Input: 6 (A0-A5), 14-bit ADC (0-16383)
- DAC: A0 (12-bit)
- Flash: 256 KB, SRAM: 32 KB
- LED Matrix: 12x8 on-board LED matrix
- I2C: SDA (A4), SCL (A5)
- Operating Voltage: 5V (but CAN bus, USB-C)
- Backward compatible with Uno R3 shields"""},

            {"title": "ESP32 Pinout (Arduino Compatible)", "category": "Board Pinout", "content": """ESP32 DevKit (Arduino-compatible):
- Microcontroller: Xtensa dual-core 240 MHz, 3.3V logic
- Wi-Fi: 802.11 b/g/n, Bluetooth: v4.2 BR/EDR + BLE
- GPIO: 34 (not all exposed), ADC: 18 channels (12-bit)
- DAC: 2 channels (8-bit), PWM: 16 channels
- Touch Pins: 10 capacitive touch inputs
- Flash: 4 MB, SRAM: 520 KB
- SPI: 3 buses, I2C: 2 buses, UART: 3
- Hall Effect Sensor, Temperature Sensor built-in
- Strapping pins (avoid): GPIO 0, 2, 5, 12, 15
- Input-only pins: GPIO 34, 35, 36, 39
- IMPORTANT: 3.3V logic, NOT 5V tolerant"""},
        ]

    def _builtin_cookbook_patterns(self):
        """Common Arduino code patterns and examples."""
        return [
            {"title": "Blink LED Pattern", "category": "Cookbook", "content": """Basic LED blink on pin 13:
```cpp
void setup() {
  pinMode(13, OUTPUT);
}
void loop() {
  digitalWrite(13, HIGH);
  delay(1000);
  digitalWrite(13, LOW);
  delay(1000);
}
```
Components: 1x LED, 1x 220-ohm resistor. Connect LED anode to pin 13, cathode to resistor, resistor to GND. Built-in LED on pin 13 needs no external components."""},

            {"title": "Fade LED with PWM", "category": "Cookbook", "content": """Fade LED using analogWrite PWM on pin 9:
```cpp
int led = 9;
int brightness = 0;
int fadeAmount = 5;
void setup() { pinMode(led, OUTPUT); }
void loop() {
  analogWrite(led, brightness);
  brightness += fadeAmount;
  if (brightness <= 0 || brightness >= 255) fadeAmount = -fadeAmount;
  delay(30);
}
```
Must use PWM pin (3, 5, 6, 9, 10, 11 on Uno). Components: LED + 220-ohm resistor."""},

            {"title": "Button Input with Debounce", "category": "Cookbook", "content": """Read button with software debounce:
```cpp
const int buttonPin = 2;
const int ledPin = 13;
int buttonState = LOW;
int lastButtonState = LOW;
unsigned long lastDebounceTime = 0;
unsigned long debounceDelay = 50;
void setup() {
  pinMode(buttonPin, INPUT_PULLUP);
  pinMode(ledPin, OUTPUT);
}
void loop() {
  int reading = digitalRead(buttonPin);
  if (reading != lastButtonState) lastDebounceTime = millis();
  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == LOW) digitalWrite(ledPin, !digitalRead(ledPin));
    }
  }
  lastButtonState = reading;
}
```
Use INPUT_PULLUP so button connects pin to GND when pressed."""},

            {"title": "Servo Motor Control", "category": "Cookbook", "content": """Control servo with potentiometer:
```cpp
#include <Servo.h>
Servo myservo;
int potPin = A0;
void setup() { myservo.attach(9); }
void loop() {
  int val = analogRead(potPin);
  int angle = map(val, 0, 1023, 0, 180);
  myservo.write(angle);
  delay(15);
}
```
Servo: signal to pin 9, red to 5V, brown/black to GND. Potentiometer: outer pins to 5V and GND, wiper to A0. Servo draws too much current from Arduino - use external 5V supply for motor."""},

            {"title": "Ultrasonic Distance Sensor (HC-SR04)", "category": "Cookbook", "content": """Measure distance with HC-SR04:
```cpp
const int trigPin = 9;
const int echoPin = 10;
void setup() {
  Serial.begin(9600);
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
}
void loop() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH);
  float distance = duration * 0.034 / 2;
  Serial.print("Distance: ");
  Serial.print(distance);
  Serial.println(" cm");
  delay(100);
}
```
HC-SR04: VCC to 5V, GND to GND, Trig to pin 9, Echo to pin 10. Range: 2-400 cm."""},

            {"title": "I2C LCD Display (16x2)", "category": "Cookbook", "content": """Display text on I2C LCD:
```cpp
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
LiquidCrystal_I2C lcd(0x27, 16, 2);
void setup() {
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Hello World!");
  lcd.setCursor(0, 1);
  lcd.print("Arduino Copilot");
}
void loop() {}
```
I2C LCD: VCC to 5V, GND to GND, SDA to A4, SCL to A5 (Uno). Common addresses: 0x27 or 0x3F. Use I2C scanner sketch if unsure."""},

            {"title": "DHT11/DHT22 Temperature Sensor", "category": "Cookbook", "content": """Read temperature and humidity:
```cpp
#include <DHT.h>
#define DHTPIN 2
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);
void setup() {
  Serial.begin(9600);
  dht.begin();
}
void loop() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  if (isnan(h) || isnan(t)) {
    Serial.println("Failed to read from DHT sensor!");
    return;
  }
  Serial.print("Humidity: "); Serial.print(h);
  Serial.print("% Temp: "); Serial.print(t); Serial.println("C");
  delay(2000);
}
```
DHT11: VCC to 5V, GND to GND, Data to pin 2 with 10K pull-up resistor to VCC. Install DHT library from Library Manager."""},

            {"title": "Non-blocking Blink (millis)", "category": "Cookbook", "content": """Blink without delay using millis():
```cpp
const int ledPin = 13;
int ledState = LOW;
unsigned long previousMillis = 0;
const long interval = 1000;
void setup() { pinMode(ledPin, OUTPUT); }
void loop() {
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    ledState = (ledState == LOW) ? HIGH : LOW;
    digitalWrite(ledPin, ledState);
  }
  // Other code can run here without being blocked
}
```
Preferred over delay() for multitasking. Allows reading sensors, checking buttons, etc. while blinking."""},

            {"title": "State Machine Pattern", "category": "Cookbook", "content": """Loop state machine for multi-step processes:
```cpp
enum State { IDLE, RUNNING, PAUSED, DONE };
State currentState = IDLE;
void setup() { Serial.begin(9600); }
void loop() {
  switch (currentState) {
    case IDLE:
      // Wait for start condition
      if (digitalRead(2) == LOW) currentState = RUNNING;
      break;
    case RUNNING:
      // Perform main task
      // Transition on condition
      break;
    case PAUSED:
      break;
    case DONE:
      currentState = IDLE;
      break;
  }
}
```
Useful for traffic lights, vending machines, robot behaviors."""},

            {"title": "MQTT IoT Publishing", "category": "Cookbook", "content": """Publish sensor data via MQTT (ESP32/WiFi boards):
```cpp
#include <WiFi.h>
#include <PubSubClient.h>
const char* ssid = "YourWiFi";
const char* password = "YourPassword";
const char* mqtt_server = "broker.emqx.io";
WiFiClient espClient;
PubSubClient client(espClient);
void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  client.setServer(mqtt_server, 1883);
}
void loop() {
  if (!client.connected()) {
    client.connect("arduinoClient");
  }
  client.loop();
  float temp = analogRead(A0) * 0.48828;
  char msg[50];
  snprintf(msg, 50, "%.2f", temp);
  client.publish("arduino/temperature", msg);
  delay(5000);
}
```
Free public broker: broker.emqx.io:1883. Install PubSubClient library."""},

            {"title": "ISR (Interrupt Service Routine) Template", "category": "Cookbook", "content": """ISR template for external interrupt:
```cpp
volatile int counter = 0;
volatile bool flag = false;
void setup() {
  Serial.begin(9600);
  pinMode(2, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(2), myISR, FALLING);
}
void myISR() {
  counter++;
  flag = true;
}
void loop() {
  if (flag) {
    noInterrupts();
    int count = counter;
    interrupts();
    Serial.print("Count: ");
    Serial.println(count);
    flag = false;
  }
}
```
Rules: ISR must be fast, no delay(), no Serial, use volatile for shared variables. Uno interrupt pins: 2 (INT0), 3 (INT1)."""},

            {"title": "Motor Control with L298N", "category": "Cookbook", "content": """Control DC motor with L298N driver:
```cpp
const int IN1 = 7;
const int IN2 = 8;
const int ENA = 9; // PWM pin for speed
void setup() {
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENA, OUTPUT);
}
void forward(int speed) {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  analogWrite(ENA, speed);
}
void backward(int speed) {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  analogWrite(ENA, speed);
}
void stopMotor() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  analogWrite(ENA, 0);
}
void loop() {
  forward(200);
  delay(2000);
  stopMotor();
  delay(500);
  backward(200);
  delay(2000);
  stopMotor();
  delay(500);
}
```
L298N: ENA to PWM pin 9, IN1 to pin 7, IN2 to pin 8. Power motor from external supply (not Arduino 5V). Common GND between Arduino and L298N."""},
        ]

    def scrape_language_reference(self):
        """Attempt to scrape Arduino docs; fall back to built-in data."""
        print("Scraping Arduino Language Reference...")
        scraped = []

        ref_urls = [
            f"{self.base_url}/language-reference/en/functions/digital-io/pinmode/",
            f"{self.base_url}/language-reference/en/functions/digital-io/digitalwrite/",
            f"{self.base_url}/language-reference/en/functions/digital-io/digitalread/",
            f"{self.base_url}/language-reference/en/functions/analog-io/analogread/",
            f"{self.base_url}/language-reference/en/functions/analog-io/analogwrite/",
            f"{self.base_url}/language-reference/en/functions/time/delay/",
            f"{self.base_url}/language-reference/en/functions/time/millis/",
            f"{self.base_url}/language-reference/en/functions/communication/serial/begin/",
            f"{self.base_url}/language-reference/en/functions/communication/serial/print/",
            f"{self.base_url}/language-reference/en/functions/external-interrupts/attachinterrupt/",
        ]

        for url in ref_urls:
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    title_tag = soup.find('h1')
                    title = title_tag.get_text(strip=True) if title_tag else url.split('/')[-2]
                    content_div = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
                    if content_div:
                        content = content_div.get_text(separator='\n', strip=True)
                        scraped.append({
                            "title": title,
                            "category": "Language Reference",
                            "content": content[:2000],
                            "source": url
                        })
                time.sleep(0.5)
            except Exception as e:
                print(f"  Warning: Could not scrape {url}: {e}")

        if scraped:
            print(f"  Scraped {len(scraped)} pages from docs.arduino.cc")
        else:
            print("  Could not reach docs.arduino.cc; using built-in reference data.")

        return scraped

    def build_knowledge_base(self):
        """Build the full knowledge base from built-in data + scraped docs."""
        print("\n=== Building Arduino Knowledge Base ===\n")

        # 1. Built-in data (always available)
        lang_ref = self._builtin_language_reference()
        pinouts = self._builtin_board_pinouts()
        cookbook = self._builtin_cookbook_patterns()

        self.docs = lang_ref + pinouts + cookbook
        print(f"  Built-in knowledge: {len(self.docs)} entries")

        # 2. Try scraping live docs
        try:
            scraped = self.scrape_language_reference()
            if scraped:
                self.docs.extend(scraped)
        except Exception as e:
            print(f"  Scraping skipped: {e}")

        # 3. Save to JSON
        output_file = self.output_dir / "arduino_knowledge_base.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.docs, f, indent=2, ensure_ascii=False)

        print(f"\n  Total knowledge entries: {len(self.docs)}")
        print(f"  Saved to: {output_file}")
        return self.docs


if __name__ == "__main__":
    scraper = ArduinoDocsScraper()
    docs = scraper.build_knowledge_base()
    print(f"\nDone! Built knowledge base with {len(docs)} entries.")
