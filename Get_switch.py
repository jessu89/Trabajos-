from netmiko import ConnectHandler
import re
import pandas as pd
import os

ROOT_SWITCH = {
    "device_type": "cisco_ios",
    "host": "192.168.1.1",  # switch core
    "username": "cisco",
    "password": "cisco99",
}

VISITADOS = set()


def limpiar():
    os.system("cls" if os.name == "nt" else "clear")


def conectar(sw):
    return ConnectHandler(**sw)


def obtener_mac_por_ip(conn, ip):
    output = conn.send_command(f"show ip arp {ip}")
    # Buscar formato como: Internet  192.168.1.10           3   001b.7842.0a00  ARPA
    m = re.search(rf"Internet\s+{re.escape(ip)}\s+\S+\s+([0-9a-fA-F\.:-]+)\s+ARPA", output)
    if not m:
        return None
    mac = m.group(1)
    # devolver en formato sin separadores (para comparar con salida de mac address-table)
    return mac.replace('.', '').replace(':', '').replace('-', '').lower()


def normalizar_mac(mac):
    mac = mac.replace('.', '').replace(':', '').replace('-', '').lower()
    if len(mac) != 12:
        return mac
    return ':'.join(mac[i:i+2] for i in range(0, 12, 2))


def buscar_mac_table(conn, mac):
    """
    Busca la MAC (sin separadores) en la tabla MAC y devuelve VLAN e interfaz.
    """
    output = conn.send_command("show mac address-table")
    mac_n = mac.lower()
    for line in output.splitlines():
        clean = line.replace('.', '').replace(':', '').replace('-', '').lower()
        if mac_n in clean:
            # intentar parsear: VLAN MAC TYPE PORT
            m = re.search(r"^(\s*\d+)\s+([0-9a-fA-F\.:-]+)\s+\S+\s+(\S+)$", line.strip())
            if m:
                vlan = m.group(1).strip()
                intf = m.group(3).strip()
                return {"vlan": vlan, "intf": intf}
            # si no concuerda regex simple por columnas
            parts = line.split()
            if len(parts) >= 4:
                return {"vlan": parts[0], "intf": parts[-1]}
    return None


def obtener_ip_cdp_por_interfaz(conn, interfaz):
    """
    Ejecuta 'show cdp neighbors <intf> detail' y extrae la IP del vecino si existe.
    Devuelve la IP como string o None.
    """
    out = conn.send_command(f"show cdp neighbors {interfaz} detail")
    # Buscar líneas con IP address: 10.0.0.1
    m = re.search(r"IP address:\s*(\d+\.\d+\.\d+\.\d+)", out)
    if m:
        return m.group(1)
    # Algunos dispositivos muestran 'IP address: 10.0.0.1' o 'Management address(es):\n  IP: 10.0.0.1'
    m2 = re.search(r"IP\s*:\s*(\d+\.\d+\.\d+\.\d+)", out)
    if m2:
        return m2.group(1)
    return None


def interfaz_es_trunk(conn, interfaz):
    """Devuelve True si la interfaz es trunk."""
    out = conn.send_command(f"show interfaces {interfaz} switchport")
    if "Administrative Mode: trunk" in out or "Operational Mode: trunk" in out:
        return True
    return False


def obtener_ip_vlan(conn, vlan):
    out = conn.send_command("show ip interface brief")
    for line in out.splitlines():
        if re.search(rf"Vlan{vlan}\b", line):
            m = re.search(r"(Vlan\d+)\s+(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                return m.group(2)
    return None


def rastrear(sw, ip_buscada):
    ruta = []
    actual = sw

    while True:
        if actual["host"] in VISITADOS:
            print(f"⚠️ Ya se visitó {actual['host']}, deteniendo bucle.")
            break
        VISITADOS.add(actual["host"])

        print(f"\n🔗 Conectando a {actual['host']} ...")
        conn = conectar(actual)
        hostname = conn.find_prompt().replace("#", "").strip()

        mac_raw = obtener_mac_por_ip(conn, ip_buscada)
        if not mac_raw:
            print(f"⚠️ No se encontró la IP {ip_buscada} en {hostname}")
            conn.disconnect()
            break

        mac_norm = normalizar_mac(mac_raw)
        print(f"✅ {hostname}: IP {ip_buscada} → MAC {mac_norm}")

        info = buscar_mac_table(conn, mac_raw)
        if not info:
            print(f"⚠️ No se encontró la MAC {mac_norm} en {hostname}")
            conn.disconnect()
            break

        vlan = info["vlan"]
        intf = info["intf"]
        print(f"🔎 MAC encontrada en {intf} (VLAN {vlan})")

        # Primero comprobar si en esa interfaz hay un vecino CDP
        vecino_ip = obtener_ip_cdp_por_interfaz(conn, intf)
        if vecino_ip:
            print(f"🔁 Se detectó vecino en {intf} con IP {vecino_ip} → conectando al switch vecino...")
            ruta.append({"sw_name": hostname, "ip_sw": actual["host"], "puerto": intf, "vlan": vlan, "next_ip": vecino_ip})
            conn.disconnect()
            # preparar conexión al vecino y repetir búsqueda de la misma IP destino
            actual = {
                "device_type": "cisco_ios",
                "host": vecino_ip,
                "username": sw["username"],
                "password": sw["password"],
            }
            continue

        # Si no hay vecino CDP, puede ser un puerto de acceso hacia el host final
        print(f"🏁 No se detectó vecino CDP en {intf}. Se asume dispositivo final conectado en {hostname}:{intf}")
        ruta.append({
            "sw_name": hostname,
            "ip_sw": actual["host"],
            "puerto": intf,
            "vlan": vlan,
            "mac_device": mac_norm,
            "ip_device": ip_buscada,
        })
        conn.disconnect()
        break

    return ruta


def menu():
    while True:
        limpiar()
        print("="*65)
        print("🔍 Rastreador de IP (detección VLAN inter-switch)")
        print("="*65)
        print("1️⃣  Buscar IP")
        print("2️⃣  Salir")
        print("="*65)
        opcion = input("Selecciona una opción: ")

        if opcion == "1":
            ip = input("Ingresa la IP del dispositivo a buscar: ").strip()
            print("\n🚀 Iniciando rastreo...\n")
            ruta = rastrear(ROOT_SWITCH, ip)

            if ruta:
                df = pd.DataFrame(ruta)
                print("\n=== RUTA COMPLETA ===")
                print(df.to_string(index=False))
                df.to_csv("ruta_busqueda_ip.csv", index=False)
                print("\n📄 Guardado en: ruta_busqueda_ip.csv")
            else:
                print("\n⚠️ No se encontró la IP en la red.")
            input("\nPresiona Enter para continuar...")
        elif opcion == "2":
            break


if __name__ == "__main__":
    menu()
