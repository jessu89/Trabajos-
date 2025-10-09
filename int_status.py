import serial
import serial.tools.list_ports
import os
import time
import pandas as pd
import textfsm

CSV_FILE = "routers_interfaces.csv"
TEMPLATE_FILE = "Value.txt"

# ╔════════════════════════════════════════════════════════════════╗
#   FUNCIONES AUXILIARES
# ╚════════════════════════════════════════════════════════════════╝

def detectar_puerto_serial():
    puertos = serial.tools.list_ports.comports()
    if not puertos:
        print("⚠ No hay puertos disponibles.")
        return None

    print("🔌 Puertos detectados:")
    for i, p in enumerate(puertos):
        print(f"{i}: {p.device} - {p.description}")

    if len(puertos) == 1:
        print(f"✅ Se detectó automáticamente: {puertos[0].device}")
        return puertos[0].device

    seleccion = input("Selecciona el número o escribe el nombre del puerto: ").strip()
    if seleccion.isdigit():
        idx = int(seleccion)
        if 0 <= idx < len(puertos):
            return puertos[idx].device
        else:
            print("⚠ Número fuera de rango.")
            return None
    else:
        return seleccion

def conectar_serial(port):
    try:
        ser = serial.Serial(port, baudrate=9600, timeout=1)
        time.sleep(2)
        print(f"✅ Conectado a {port}")
        return ser
    except Exception as e:
        print(f"❌ Error al conectar: {e}")
        return None

def send_command(ser, cmd, delay=2):
    ser.reset_input_buffer()
    ser.write((cmd + "\r\n").encode())
    time.sleep(delay)
    output = ser.read(ser.in_waiting).decode(errors="ignore")
    return output.strip()

# ╔════════════════════════════════════════════════════════════════╗
#   FUNCIONES PRINCIPALES
# ╚════════════════════════════════════════════════════════════════╝

def get_hostname(ser):
    output = send_command(ser, "\n")
    if "#" in output:
        return output.split("#")[0].strip()
    else:
        send_command(ser, "show run | i hostname")
        output = send_command(ser, "show run | i hostname")
        if "hostname" in output:
            return output.split("hostname")[-1].strip()
    return "Desconocido"

def obtener_interfaces_textfsm(ser):
    if not os.path.exists(TEMPLATE_FILE):
        print(f"⚠ No se encontró el template: {TEMPLATE_FILE}")
        print("Crea este archivo con el contenido correcto para 'show ip interface brief'.")
        return None

    print("📡 Ejecutando 'show ip interface brief'...")
    output = send_command(ser, "show ip interface brief", delay=3)
    with open(TEMPLATE_FILE) as template:
        fsm = textfsm.TextFSM(template)
        try:
            result = fsm.ParseText(output)
            headers = fsm.header
            df = pd.DataFrame(result, columns=headers)
            return df
        except Exception as e:
            print(f"⚠ Error al parsear: {e}")
            print("Salida cruda del dispositivo:")
            print(output)
            return None

def guardar_interfaces_en_csv(hostname, df):
    if df is None or df.empty:
        print("⚠ No hay datos para guardar.")
        return

    # Aplanar la info en una sola fila
    data = {"Hostname": hostname}
    for i, row in df.iterrows():
        for col in df.columns:
            data[f"{col}_{i+1}"] = row[col]

    # --- 🔧 CORRECCIÓN AQUÍ ---
    if os.path.exists(CSV_FILE):
        df_csv = pd.read_csv(CSV_FILE)

        # Si ya existe el hostname, actualiza esa fila
        if hostname in df_csv["Hostname"].values:
            idx = df_csv.index[df_csv["Hostname"] == hostname][0]
            for k, v in data.items():
                df_csv.loc[idx, k] = v
        else:
            # Agrega un nuevo router
            df_csv = pd.concat([df_csv, pd.DataFrame([data])], ignore_index=True)
    else:
        # Si no existe el archivo, créalo con el router actual
        df_csv = pd.DataFrame([data])

    # Rellenar NaN con vacío para evitar errores de escritura
    df_csv = df_csv.fillna("")

    df_csv.to_csv(CSV_FILE, index=False)
    print(f"✅ Datos guardados/actualizados en {CSV_FILE}")

# ╔════════════════════════════════════════════════════════════════╗
#   MENÚ
# ╚════════════════════════════════════════════════════════════════╝

def menu():
    port = detectar_puerto_serial()
    if not port:
        return
    ser = conectar_serial(port)
    if not ser:
        return

    while True:
        print("""
╔════════════════════════════════════════╗
║              MENÚ PRINCIPAL             ║
╚════════════════════════════════════════╝
1. Comandos manuales
2. Obtener interfaces
0. Salir
""")
        opcion = input("Selecciona una opción: ").strip()

        if opcion == "1":
            while True:
                cmd = input("Router# ").strip()
                if cmd.lower() in ["exit", "salir"]:
                    break
                output = send_command(ser, cmd, delay=2)
                print(output)

        elif opcion == "2":
            hostname = get_hostname(ser)
            print(f"🔹 Hostname detectado: {hostname}")
            df = obtener_interfaces_textfsm(ser)
            if df is not None:
                guardar_interfaces_en_csv(hostname, df)
            else:
                print("⚠ No se pudieron extraer interfaces.")
            input("Presiona ENTER para volver al menú...")

        elif opcion == "0":
            ser.close()
            print("👋 Conexión cerrada.")
            break
        else:
            print("❌ Opción inválida.")
            time.sleep(1)

# ╔════════════════════════════════════════════════════════════════╗
#   MAIN
# ╚════════════════════════════════════════════════════════════════╝
if __name__ == "__main__":
    menu()
