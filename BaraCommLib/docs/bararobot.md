# BaraRobot Class (High-Level API)

La classe `BaraRobot` è l'entry point principale della libreria. È progettata per nascondere la complessità dell'hardware sottostante e offrire un'interfaccia "commercial-like", pulita, sicura e pronta all'uso.

Una volta istanziato, `BaraRobot` legge automaticamente il file `baraconfig.yaml`, avvia i motori, fa il setup dei pin e lancia in background i thread di I2C per il caching super-veloce dei sensori.

```python
from baracommlib.BaraRobot import BaraRobot

# Inizializza tutto l'hardware definito nel YAML in modo automatico
robot = BaraRobot("baraconfig.yaml")
```

---

## 1. Motori e Drivetrain (`robot.drivetrain`)
Il modulo `drivetrain` (basato sulla classe `Motors`) è pre-configurato e pronto all'uso.
Tiene in considerazione la configurazione di motori invertiti fisicamente senza dover cambiare il codice logico.

```python
# Movimenti di base
robot.drivetrain.move_forward_action(speed=80)
robot.drivetrain.turn_left_action(speed=50)

# Frenata (Coast: stacca la corrente; Force Brake: frena elettricamente)
robot.drivetrain.coast()
robot.drivetrain.force_brake(max_pwm_value=100)

# Controllo manuale del singolo motore
from baracommlib.Motors import Motor
robot.drivetrain.assign_manual_power(Motor.A, power=70)
```

---

## 2. Sensori: Accesso Istantaneo $O(1)$ (`robot.sensor`)
La gestione dei sensori avviene in background. Quando chiami un metodo da `robot.sensor`, ottieni il valore **istantaneamente** dall'ultimo ciclo di lettura senza bloccare il thread principale (cruciale per algoritmi come i PID).

L'interfaccia proxy di `robot.sensor` espone tre comodi metodi:

### `get(sensor_id)`
Ritorna il valore dell'ultimo campionamento del sensore specificato nel YAML tramite il suo ID univoco.

```python
# Lettura frontale (ToF)
distanza = robot.sensor.get("front") # Esempio: 152.0

# Lettura giroscopica (IMU)
gyro = robot.sensor.get("main_gyro")
# Esempio: {"yaw": 45.1, "pitch": 0.2, "roll": 1.5}
```

### `get_by_direction(direction)`
Se hai raggruppato più sensori sotto la stessa "direzione" nel YAML (es. due sensori diagonali `FRONT_LEFT` e `FRONT_RIGHT` mappati entrambi logicamente come `FRONT` per un sensore generale), puoi ottenere tutti i loro valori in un dizionario. Accetta stringhe ("front") o Enum.

```python
valori_frontali = robot.sensor.get_by_direction("front")
# Expected: {"front_dx": 120, "front_sx": 118}
```

### `get_average_by_direction(direction)`
Prende tutti i sensori che puntano in una certa direzione, scarta quelli rotti (che ritornano `None`) ed esegue automaticamente una media matematica per darti una stima robusta e ripulita dal rumore o dai guasti hardware.

```python
media_distanza = robot.sensor.get_average_by_direction("front")
if media_distanza is not None and media_distanza < 100:
    print("Muro vicino!")
```

---

## 3. Gestione Eventi e Bottoni
Non dovrai più inquinare il tuo loop principale con `if GPIO.input(PIN): ...` con il rischio di letture fluttuanti. La libreria gestisce per te il **debouncing** e il multithreading.

### Decoratore Asincrono
Aggiungi `@robot.on_button_pressed` sopra a una funzione. La libreria creerà un thread dedicato per ascoltare in background le interazioni dell'utente in totale sicurezza.

```python
@robot.on_button_pressed("start")
def avvia_routine():
    print("Il robot ha rilevato il tocco dell'utente!")
    # Qui il codice scatterà solo una volta per pressione, grazie al debouncing automatico.
```

### Lettura Sincrona
Se preferisci controllare lo stato del bottone all'interno di uno statemachine, puoi usare la funzione sincrona:
```python
if robot.is_button_pressed("start"):
    print("Pulsante tenuto premuto in questo istante.")
```

---

## 4. Movimento Avanzato (Navigazione Relativa)
Avendo integrato nativamente un layer di sensor fusion giroscopico, `BaraRobot` offre una comoda API per girare di gradi precisi sul posto.

```python
# Gira a DESTRA di 90 gradi con velocità 50.
# Blocca l'esecuzione finché il turno non è completato con una precisione (tolleranza) di 2°.
robot.turn(angle=90.0, speed=50, tolerance=2.0)

# Gira a SINISTRA di 45 gradi
robot.turn(angle=-45.0)
```

---

## 5. Teardown e Pulizia Sicura (`cleanup`)
Quando l'applicazione termina, è **obbligatorio** spegnere i motori e rilasciare le risorse I2C. `BaraRobot` integra una solida implementazione del garbage collection (`__del__`), il che significa che alla chiusura dello script la libreria tenta in autonomia di ripulire le risorse.

Tuttavia, è "best practice" chiamarlo esplicitamente alla fine del main loop. Questo garantisce che i motori non impazziscano continuando a ricevere vecchi segnali PWM in caso di crash.

```python
try:
    while True:
        pass # Il tuo codice...
except KeyboardInterrupt:
    pass
finally:
    # Ferma motori, spegne i thread sensori e ripulisce il GPIO
    robot.cleanup()
```
