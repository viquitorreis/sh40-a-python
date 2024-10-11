# sensirion docs https://sensirion.github.io/python-i2c-sht4x/execute-measurements.html#example-script
import argparse
import random
from time import sleep
from sensirion_i2c_driver import LinuxI2cTransceiver, I2cConnection, CrcCalculator
from sensirion_driver_adapters.i2c_adapter.i2c_channel import I2cChannel
from sensirion_i2c_sht4x.device import Sht4xDevice

parser = argparse.ArgumentParser()
parser.add_argument('--i2c-port', '-p', default='/dev/i2c-1')
args = parser.parse_args()

def simulate_data():
    """Simulate sensor data (temperature and humidity)."""
    temperature = round(random.uniform(20.0, 25.0), 2)
    humidity = round(random.uniform(40.0, 60.0), 2)
    return temperature, humidity

def read_sht40(sensor):
    """Read temperature and humidity from the SHT40 sensor."""
    try:
        (temperature, humidity) = sensor.measure_lowest_precision()
        return temperature, humidity
    except Exception as e:
        print(f"Error reading from sensor: {e}")
        return None, None

def main():
    i2c_transceiver = LinuxI2cTransceiver(args.i2c_port)

    channel = I2cChannel(
        I2cConnection(i2c_transceiver),
        slave_address=0x44,
        crc=CrcCalculator(8, 0x31, 0xff, 0x0)
    )

    sensor = Sht4xDevice(channel)

    try:
        sensor.soft_reset()
        sleep(0.01)
    except Exception as e:
        print(f"Soft reset failed: {e}")

    try:
        serial_number = sensor.serial_number()
        print(f"Sensor Serial Number: {serial_number}")
    except Exception as e:
        print(f"Could not read serial number: {e}")

    while True:
        try:
            temperature, humidity = read_sht40(sensor)
            if temperature is None and humidity is None:
                print("Simulating data...")
                temperature, humidity = simulate_data()
        except Exception as e:
            print(f"Unexpected error: {e}. Using simulated data.")
            temperature, humidity = simulate_data()

        print(f"Temperature: {temperature} °C, Humidity: {humidity} %")

        sleep(5)

if __name__ == "__main__":
    main()
