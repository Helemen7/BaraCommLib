import time
import sys
import os

from baracommlib.BaraRobot import BaraRobot


def main():
    print("Inizializzazione Robot in corso...")
    # Il robot viene creato usando il file baraconfig.yaml in questa stessa cartella    (la prima volta potrebbe dare errore se non si è creata la config, nessun problema)
    robot = BaraRobot(config_filepath="baraconfig.yaml")
    
    # 1. ESEMPIO BOTTONE: Usiamo il decoratore per reagire al bottone "start" configurato nel YAML
    @robot.on_button_pressed("start")
    def on_start_button():
        print("\n[!] Bottone 'start' premuto! Eseguo una rotazione di 90 gradi a destra...")
        try:
            # Sfrutta il giroscopio per girare esattamente di 90 gradi con tolleranza di 2 gradi
            robot.turn(angle=90.0, speed=50, tolerance=2.0)
            print("[!] Rotazione completata.")
        except RuntimeError as e:
            print(f"[!] Impossibile ruotare: {e}")

    print("Robot inizializzato correttamente.")
    print("Premi CTRL+C per fermare il programma.")
    print("Attesa comando... (premi il bottone 'start' per ruotare o metti un ostacolo davanti)\n")

    # Flag per evitare spam in console
    was_obstructed = False

    try:
        # Loop Principale (Application Loop)
        while True:
            # 2. LETTURA SENSORI: I valori vengono letti in O(1) dalla cache dei thread in background
            front_distance = robot.sensor.get("front") # Il sensore ToF frontale nel YAML
            gyro_data = robot.sensor.get("main_gyro")
            
            # Formattazione sicura per il print
            dist_str = f"{front_distance} mm" if front_distance is not None else "N/A"
            yaw_str = f"{gyro_data['yaw']:.1f}°" if (gyro_data and isinstance(gyro_data, dict)) else "N/A"
            
            # 3. LOGICA DI MOVIMENTO: Semplice Obstacle Avoidance
            if front_distance is not None and front_distance < 150.0:
                if not was_obstructed:
                    print(f"\n[AVVISO] Ostacolo rilevato a {dist_str}! Freno immediatamente.")
                    was_obstructed = True
                
                # Frena i motori
                robot.drivetrain.coast()
            else:
                if was_obstructed:
                    print("\n[AVVISO] Via libera. Riprendo la marcia.")
                    was_obstructed = False
                
                # Muove i motori in avanti
                robot.drivetrain.move_forward_action(speed=30)
                
                # Stampa lo stato in modo compatto (sovrascrivendo la riga)
                print(f"\rIn marcia - Distanza: {dist_str} | Heading Gyro: {yaw_str}    ", end="", flush=True)

            # Il loop può girare molto velocemente, aggiungiamo uno sleep per non saturare la CPU
            time.sleep(0.05)

    except KeyboardInterrupt:
        # Questo cattura la pressione di CTRL+C
        print("\n\nSpegnimento del programma richiesto dall'utente...")
        
    finally:
        # 4. CLEANUP CRITICO: Va SEMPRE messo nel block "finally" 
        # Assicura che i pin GPIO vengano rilasciati, i thread fermati e i motori spenti.
        print("Eseguo la pulizia hardware (cleanup)...")
        robot.cleanup()
        print("Cleanup completato. Arrivederci!")

if __name__ == "__main__":
    main()
