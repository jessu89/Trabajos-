import serial
import serial.tools.list_ports
import pandas as pd
import os
import textfsm

# ╔════════════════════════════════════════════════════════════════╗
#   FUNCIONES AUXILIARES
# ╚════════════════════════════════════════════════════════════════╝

def detectar_puerto_serial():
    puertos = list(serial.tools.list_ports.comports())
    if not puertos:
        print("⚠ No se detectaron puertos COM disponibles.")
        return None
    return puertos[0].device  # Usar el primero disponible automáticamente

def conectar_router():
    puerto = detectar_puerto_serial()
    if not puerto:
        return None
    try:
        ser = serial.Serial(puerto, baudrate=9600, timeout=1)
        print(f"✅ Conectado exitosamente a {puerto}")
        return ser
    except Exception as e:
        print(f"❌ Error al conectar con el puerto {puerto}: {e}")
        return None

def enviar_comando(ser, comando):
    ser.write((comando + "\n").encode())
    ser.flush()
    salida = ""
    while True:
        linea = ser.readline().decode(errors="ignore")
        if not linea:
            break
        salida += linea
    return salida.strip()

# ╔════════════════════════════════════════════════════════════════╗
#   FUNCIÓN PARA PARSEAR Y GUARDAR EN CSV (una fila por router)
# ╚════════════════════════════════════════════════════════════════╝

def obtener_interfaces_csv_fila(ser):
    # Obtener hostname
    hostname_out = enviar_comando(ser, "show running-config | include hostname")
    hostname = hostname_out.split()[-1] if "hostname" in hostname_out else "Desconocido"
    print(f"🔹 Hostname detectado: {hostname}")

    # Ejecutar show ip interface brief
    salida = enviar_comando(ser, "show ip interface brief")
    print(salida)

    # Template TextFSM
    template_path = os.path.join(os.getcwd(), "Value.txt")
    if not os.path.exists(template_path):
        print(f"⚠ No se encontró el template: {template_path}")
        return

    with open(template_path) as template:
        fsm = textfsm.TextFSM(template)
        resultados = fsm.ParseText(salida)

    if not resultados:
        print("⚠ No se pudieron extraer interfaces.")
        return

    # Crear diccionario para una sola fila
    fila = {"Hostname": hostname}
    for i, r in enumerate(resultados, start=1):
        interface, ip, ok, method, status, protocol = r
        fila[f"Interface_{i}"] = interface
        fila[f"IP_{i}"] = ip
        fila[f"Status_{i}"] = status
        fila[f"Protocol_{i}"] = protocol

    csv_file = "interfaces_una_fila.csv"
    if os.path.exists(csv_file):
        df_existente = pd.read_csv(csv_file)
        df_final = pd.concat([df_existente, pd.DataFrame([fila])], ignore_index=True)
    else:
        df_final = pd.DataFrame([fila])

    df_final.to_csv(csv_file, index=False)
    print(f"\n✅ Datos guardados correctamente en '{csv_file}'\n")

# ╔════════════════════════════════════════════════════════════════╗
#   MENÚ PRINCIPAL
# ╚════════════════════════════════════════════════════════════════╝

def menu():
    ser = conectar_router()
    if not ser:
        return

    while True:
        print("""
╔════════════════════════════════════════════╗
║             MENÚ PRINCIPAL                ║
╚════════════════════════════════════════════╝
1. Comandos manuales
2. Obtener interfaces (TextFSM, una fila)
0. Salir
""")
        opcion = input("Selecciona una opción: ")
        if opcion == "1":
            while True:
                cmd = input("Router# ")
                if cmd.lower() == "exit":
                    break
                salida = enviar_comando(ser, cmd)
                print(salida)
        elif opcion == "2":
            obtener_interfaces_csv_fila(ser)
            input("Presiona ENTER para volver al menú...")
        elif opcion == "0":
            ser.close()
            break
        else:
            print("⚠ Opción no válida.")

# ╔════════════════════════════════════════════════════════════════╗
#   MAIN
# ╚════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    menu()
