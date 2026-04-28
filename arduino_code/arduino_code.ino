#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Initialize the LCD with I2C address 0x27 and 24x4 size
LiquidCrystal_I2C lcd(0x27, 24, 4);

void setup() {
  lcd.init();
  lcd.backlight();

  // Boot splash
  lcd.setCursor(0, 0);
  lcd.print("PC HEALTH MONITOR");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");

  delay(2000);
  lcd.clear();

  // Start serial communication
  Serial.begin(9600);
}

void loop() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n');

    // Find positions of each metric in the incoming packet
    int cpuIndex   = data.indexOf("CPU:");
    int ramIndex   = data.indexOf("RAM:");
    int diskIndex  = data.indexOf("DISK:");
    int gtempIndex = data.indexOf("gTEMP:");
    int gpuIndex   = data.indexOf("GPU:");
    int gpwrIndex  = data.indexOf("gPWR:");
    int ctempIndex = data.indexOf("cTEMP:");

    if (cpuIndex != -1 && ramIndex != -1 && diskIndex != -1 &&
        gtempIndex != -1 && gpuIndex != -1 &&
        gpwrIndex != -1 && ctempIndex != -1) {

      // Extract each value using key-prefix protocol
      String cpuUsage  = data.substring(cpuIndex  + 4, ramIndex   - 1);
      String ramUsage  = data.substring(ramIndex   + 4, diskIndex  - 1);
      String diskUsage = data.substring(diskIndex  + 5, gtempIndex - 1);
      String gtemp     = data.substring(gtempIndex + 6, gpuIndex   - 1);
      String gpuUsage  = data.substring(gpuIndex   + 4, gpwrIndex  - 1);
      String gpwr      = data.substring(gpwrIndex  + 5, ctempIndex - 1);
      String ctemp     = data.substring(ctempIndex + 6);

      lcd.clear();

      // Row 0: CPU and GPU load
      lcd.setCursor(0, 0);
      lcd.print("CPU:" + cpuUsage);
      lcd.setCursor(12, 0);
      lcd.print("GPU:" + gpuUsage);

      // Row 1: Disk and RAM
      lcd.setCursor(0, 1);
      lcd.print("DISK:" + diskUsage);
      lcd.setCursor(12, 1);
      lcd.print("RAM:" + ramUsage);

      // Row 2: CPU temp and GPU temp
      lcd.setCursor(0, 2);
      lcd.print("cTEMP:" + ctemp + "C");
      lcd.setCursor(10, 2);
      lcd.print("gTEMP:" + gtemp + "C");

      // Row 3: GPU power
      lcd.setCursor(0, 3);
      lcd.print("gPWR:" + gpwr);
    }
  }
}
