  const int fsr1Pin = A0;                                                       
  const int fsr2Pin = A1;
  const int fsr3Pin = A2;
  const int fsr4Pin = A3;
  const int fsr5Pin = A4;
  
                                                                                
  void setup() {  
    Serial.begin(9600);                                                        
  }
                                                                                
  void loop() {
    int fsr1Value = analogRead(fsr1Pin);                                        
    int fsr2Value = analogRead(fsr2Pin);
    int fsr3Value = analogRead(fsr3Pin);
    int fsr4Value = analogRead(fsr4Pin);
    int fsr5Value = analogRead(fsr5Pin);

    Serial.print("FSR1: ");
    Serial.print(fsr1Value);
    Serial.print("  FSR2: ");
    Serial.print(fsr2Value);
    Serial.print("  FSR3: ");
    Serial.print(fsr3Value);
    Serial.print("  FSR4: ");
    Serial.print(fsr4Value);
    Serial.print("  FSR5: ");
    Serial.println(fsr5Value);
                                                                                
    delay(10);   
  }