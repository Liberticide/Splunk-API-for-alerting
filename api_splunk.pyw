import tkinter as tk
from tkinter import messagebox
from xml.dom import minidom
import json, requests, os, threading, time

# déclaration des variables globales
version = '0.8.4'
status_count = ""
config_splunk_url = "https://server.splunk.exemple:8089"
config_splunk_username = "admin"
config_splunk_query = '| makeresults count=50 | streamstats count AS NB \
| eval host="RH".NB \
| eval Critical=90, Warning=80, load=random() % 100 \
| eval status=case(load>=Critical, "Critical", load>=Warning, "Warning", load<Warning AND load>=0, "OK", true(), "Unknown") \
| eval summary_type="status_CPU", detail="Alerte CPU!!!!!!!!!!" \
| eval Time=strftime(_time, "%Y-%m-%d %Hh%Mm%Ss") \
| table Time summary_type host status load Warning Critical detail \
| sort status host summary_type'
config_interval = "5"

# création d'une fonction about
def about():
    messagebox.showinfo("About", "API Splunk v{}".format(version))


# création d'une fonction d'encodage du mot de passe (pour éviter de stocker le mot de passe en clair dans le fichier de configuration)
# la fonction encode le mot de passe en décalant chaque caractère de 128 places
def encode_password(password):
    encoded_password = ""
    for c in password:
        encoded_password += chr(ord(c) + 128)
    return encoded_password


# création d'une fonction de décodage du mot de passe (pour éviter de stocker le mot de passe en clair dans le fichier de configuration)
# la fonction décode le mot de passe en décalant chaque caractère de 128 places
def decode_password(encoded_password):
    decode_password = ""
    for c in encoded_password:
        decode_password += chr(ord(c) - 128)
    return decode_password


# création d'une fonction de sauvegarde des paramètres de connexion
def save_config():
    # récupération des paramètres de connexion saisis
    splunk_url = url_entry.get()
    splunk_username = username_entry.get()
    splunk_password = encode_password(password_entry.get())
    query = query_entry.get()
    interval = int(interval_var.get()) * 60

    # création d'un dictionnaire avec les paramètres de connexion
    config = {
        "splunk_url": splunk_url,
        "splunk_username": splunk_username,
        "splunk_password": splunk_password,
        "query": query,
        "interval": interval
    }

    # sauvegarde des paramètres de connexion dans le fichier splunk_api.config.json et création du fichier si il n'existe pas
    # le fichier splunk_api.config.json est créé dans le même répertoire que le script
    with open(os.path.join(os.path.expanduser('~'), "splunk_api.config.json"), "w") as f:
        json.dump(config, f)

    # affichage d'un message de confirmation
    messagebox.showinfo("Confirmation", "Configuration sauvegardée")


# création d'une fonction de chargement des paramètres de connexion
def load_config():
        if os.path.isfile(os.path.join(os.path.expanduser('~'), "splunk_api.config.json")):
            # chargement des paramètres de connexion depuis le fichier splunk_api.config.json
            with open(os.path.join(os.path.expanduser('~'), "splunk_api.config.json"), "r") as f:
                config = json.load(f)

            count=0
            
            # affichage des paramètres de connexion dans les champs de saisie
            if "splunk_url" in config:
                url_entry.delete(0, tk.END)
                url_entry.insert(0, config["splunk_url"])
            else:
                count=count+1
            if "splunk_username" in config:
                username_entry.delete(0, tk.END)
                username_entry.insert(0, config["splunk_username"])
            else:
                count=count+1
            if "splunk_password" in config:
                password_entry.delete(0, tk.END)
                password_entry.insert(0, decode_password(config["splunk_password"]))
            else:
                count=count+1
            if "query" in config:
                query_entry.delete(0, tk.END)
                query_entry.insert(0, config["query"])
            else:
                count=count+1
            if "interval" in config:
                interval_var.set(str(config["interval"] // 60))
            else:
                count=count+1
            
            if count==0:
                send_query()

        else:
            messagebox.showinfo("Information", "Le fichier splunk_api.config.json n'existe pas, les paramètres par défaut sont utilisés")


# création d'une fonction de connexion à l'API Splunk
def connect():
    global splunk_token

    # Récupération des paramètres de connexion saisis
    splunk_url = url_entry.get()
    splunk_username = username_entry.get()
    splunk_password = password_entry.get()

    # Envoi de la requête GET à l'API Splunk 
    response = requests.get(
        "{}/services/auth/login".format(splunk_url),
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'},
        data={"username": splunk_username, "password": splunk_password},
        verify=False
    )

    # Vérification de la réponse de l'API
    if response.status_code == 200:
        # Récupération du token de session dans la réponse xml de l'API
        xmldoc = minidom.parseString(response.text)
        itemlist = xmldoc.getElementsByTagName('sessionKey')
        splunk_token = itemlist[0].firstChild.nodeValue
    
    # Affichage d'un message d'erreur si la connexion a échoué
    else:
        messagebox.showerror("Erreur", "Erreur lors de la connexion à l'API Splunk : {}".format(response.text))


# création d'une fonction d'envoi de la requête à l'API Splunk
def send_query():

    global status_count

    # Récupération des paramètres de connexion saisis
    splunk_url = url_entry.get()
    query = query_entry.get()
    interval = int(interval_var.get()) * 60

    # test si le token est définit
    try:
        splunk_token
    except NameError:
        # creation du token
        connect()

    # Envoi de la requête GET à l'API Splunk
    response = requests.get(
        "{}/services/search/jobs/export".format(splunk_url),
        #auth=(splunk_username, splunk_password),
        headers = { 'Authorization': ('Splunk %s' %splunk_token)},
        params={"search": query, "output_mode": "json_rows", "preview": "false"},
        verify=False
    )
    # Vérification de la réponse de l'API
    if response.status_code != 200:
        messagebox.showerror("Erreur", "Erreur lors de la requête à l'API Splunk : {}".format(response.text))
    else:
        # Vérification du format de la réponse      
        # verifi si la valeur de reponse.text est au format json
        try:
            data = json.loads(response.text)
        except ValueError:
            messagebox.showerror("Erreur", "Erreur dans le format de données JSON : {}".format(response.text))
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, response.text)
            return

        result_text.delete(1.0, tk.END)

        # on compte le nombre maximum de caractères du champ "fields" et "row" par colonne et on stocke le résultat dans la variable "max_char"
        max_char = {}
        if "fields" in data:
            for i in range(len(data["fields"])):
                max_char[i] = len(data["fields"][i])
            for row in data["rows"]:
                for i in range(len(row)):
                    if len(row[i]) > max_char[i]:
                        max_char[i] = len(row[i])
        else:
            messagebox.showinfo("Information", "La requête n'a pas retourné de résultat")
            return
        
        # affichage des données reçues
        # le champ "fields" contient les nom des colonnes
        # chaque valeur de "fields" est une liste de valeurs correspondant aux colonnes
        # si le champ "fields" n'est pas présent, c'est que la requête n'a pas retourné de résultat
        if "fields" in data:
            # on affiche les noms des colonnes, chaque valeur doit avoir une largeur de caractère égale à la valeur du dictionnaire "max_char"
            for i in range(len(data["fields"])):
                data["fields"][i] = data["fields"][i] + " " * (max_char[i] - len(data["fields"][i]))
            # on affiche les noms des colonnes dans le champ "result_text"
            result_text_format = " | ".join(data["fields"])
            result_text.insert(tk.END, result_text_format.replace("{", "").replace("}", ""))
            result_text.insert(tk.END, "\n")
            # on supprime la valeur de result_text_format pour éviter qu'elle ne s'affiche plusieurs fois
            result_text_format = ""

            # le champ "rows" contient les données
            # chaque valeur de "rows" est une liste de valeurs correspondant aux colonnes
            # chaque valeur de la liste est séparée par un pipe
            # si le champ "rows" n'est pas présent, c'est que la requête n'a pas retourné de résultat
            # si la valeur ce la colonne status et égale à "Critical", on change la couleur de fond de la ligne en rouge
            # si la valeur ce la colonne status et égale à "Warning", on change la couleur de fond de la ligne en jaune
            # si la valeur ce la colonne status et égale à "OK", on change la couleur de fond de la ligne en vert
            # si la valeur ce la colonne status et égale à "Unknown", on change la couleur de fond de la ligne en gris
            if "rows" in data:
                for i in range(len(data["rows"])):
                    for j in range(len(data["rows"][i])):
                        data["rows"][i][j] = data["rows"][i][j] + " " * (max_char[j] - len(data["rows"][i][j]))
                    result_text_format = " | ".join(data["rows"][i])
                    if "Critical" in result_text_format:
                        result_text.insert(tk.END, result_text_format.replace("{", "").replace("}", ""), "Critical")
                        result_text.tag_config("Critical", background="red", selectbackground="blue", selectforeground="white", foreground="white")
                    elif "Warning" in result_text_format:
                        result_text.insert(tk.END, result_text_format.replace("{", "").replace("}", ""), "Warning")
                        result_text.tag_config("Warning", background="yellow", selectbackground="blue", selectforeground="white")
                    elif "OK" in result_text_format:
                        result_text.insert(tk.END, result_text_format.replace("{", "").replace("}", ""), "OK")
                        result_text.tag_config("OK", background="green", selectbackground="blue", selectforeground="white", foreground="white")
                    elif "Unknown" in result_text_format:
                        result_text.insert(tk.END, result_text_format.replace("{", "").replace("}", ""), "Unknown")
                        result_text.tag_config("Unknown", background="grey", selectbackground="blue", selectforeground="white")
                    result_text.insert(tk.END, "\n")
                    result_text_format = "" 

            # comptage du nombre de lignes par "status", les "status" possibles sont "Critical", "Warning", "OK" et "Unknown"
            # la données sont stockées dans le dictionnaire "status_count"
            # on initialise le dictionnaire avec les "status" possibles et on leur donne la valeur 0
            status_count = {"Critical": 0, "Warning": 0, "OK": 0, "Unknown": 0}
            
            # on compte le nombre de "status" dans la colonne "status" de la variable "data["row"]"
            # pour trouver la colonne "status", on parcours la liste "data["fields"]" et on vérifie si la valeur de la colonne est égale à "status"
            # si la valeur de la colonne est égale à "status", on récupère l'index de la colonne
            # on parcours la liste "data["rows"]" et on vérifie si la valeur de la colonne "status" est égale à "Critical", "Warning", "OK" ou "Unknown"
            # si la valeur de la colonne "status" est égale à "Critical", "Warning", "OK" ou "Unknown", on incrémente la valeur du dictionnaire "status_count"
            for i in range(len(data["fields"])): 
                if "status" in data["fields"][i]:
                    status_index = i
            for i in range(len(data["rows"])): 
                if "Critical" in data["rows"][i][status_index]:
                    status_count["Critical"] += 1
                elif "Warning" in data["rows"][i][status_index]:
                    status_count["Warning"] += 1
                elif "OK" in data["rows"][i][status_index]:
                    status_count["OK"] += 1
                elif "Unknown" in data["rows"][i][status_index]:
                    status_count["Unknown"] += 1

                # on affiche le nombre de lignes par "status" dans la zone de texte "status_text"
                # on supprime le contenu de la zone de texte "status_text" avant d'afficher les données
                status_text_critical.delete(1.0, tk.END)
                status_text_warning.delete(1.0, tk.END)
                status_text_ok.delete(1.0, tk.END)
                status_text_unknown.delete(1.0, tk.END)

                status_text_critical.insert(tk.END, "Critical: " + str(status_count["Critical"]))
                status_text_warning.insert(tk.END, "Warning: " + str(status_count["Warning"]))
                status_text_ok.insert(tk.END, "OK: " + str(status_count["OK"]))
                status_text_unknown.insert(tk.END, "Unknown: " + str(status_count["Unknown"]))

        else:
            result_text.insert(tk.END, "Aucun résultat")
        
        # adaptation de la largeur de la zone de texte en fonction du nombre de caractères des colonnes
        line_width = 8*23
        if max_char != []:
            line_width = 0
            for i in max_char:
                line_width += max_char[i]+3
        
        # on limite la largeur de la zone de texte à 210 caractères et on active le défilement horizontal
        if line_width < 210:
            result_text.config(width=line_width, font=("Courier", 10))
        else:
            result_text.config(width=210, font=("Courier", 10))
                
        # adaptation de la hauteur de la zone de texte en fonction du nombre de lignes
        # on ajoute 1 à la hauteur pour afficher la ligne des noms des colonnes
        # la hauteur de la zone de texte est limitée à 20 lignes
        if len(data["rows"]) < 40:
            result_text.config(height=len(data["rows"])+2)
        else:
            result_text.config(height=40)

    # Programmation de la prochaine exécution de la fonction après un intervalle de temps donné
    root.after(interval*1000, send_query)

# Création de la fenêtre principale, la fenêtre principale ne peut pas être redimensionnée
root = tk.Tk()
root.title("API Splunk")
root.resizable(False, False)

# fonction d' affichage de la fenêtre au premier plan et supprimer les bordures
def first_plan():
    root.attributes("-topmost", True)
    root.overrideredirect(True)


# creation d'une fonction, qui va vérifier si la fenêtre est en mode caché ou non
# si le bouton "show_button" est égale à "afficher", la fonction va verifier si la fenêtre est au premier plan
def check_hide():
    while show_button.cget("text") == "Afficher":
        first_plan()
        time.sleep(0.1)


# creation d'une fonction pour cacher et afficher les entrées 
def hide_show():
    if show_button.cget("text") == "Cacher":

        # affichage de la fenêtre au premier plan et suppression des bordures
        first_plan()

        # suppression des widgets
        url_label.grid_remove()
        url_entry.grid_remove()
        username_label.grid_remove()
        username_entry.grid_remove()
        password_label.grid_remove()
        password_entry.grid_remove()
        interval_label.grid_remove()
        interval_menu.grid_remove()
        query_label.grid_remove()
        query_entry.grid_remove()
        result_label.grid_remove()
        result_text.grid_remove()
        scrollbar.grid_remove()
        scrollbar_x.grid_remove()
        send_button.grid_remove()

        # affichage des widgets des "status"
        status_label.grid(row=5, column=3, padx=5, pady=5)
        status_text_critical.grid(row=5, column=4, padx=5, pady=5)
        status_text_warning.grid(row=5, column=5, padx=5, pady=5)
        status_text_ok.grid(row=5, column=6, padx=5, pady=5)
        status_text_unknown.grid(row=5, column=7, padx=5, pady=5)

        # modification du texte du bouton "show_button"
        show_button.config(text="Afficher")

        # suppression du menu
        delete_menu()

    else:
        root.attributes("-topmost", False)
        root.overrideredirect(False)

        # affichage des widgets
        url_label.grid(row=0, column=0, padx=5, pady=5)
        url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        username_label.grid(row=1, column=0, padx=5, pady=5)
        username_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        password_label.grid(row=2, column=0, padx=5, pady=5)
        password_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        interval_label.grid(row=4, column=0, padx=5, pady=5)
        interval_menu.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        query_label.grid(row=3, column=0, padx=5, pady=5)
        query_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        result_label.grid(row=7, column=0, padx=5, pady=5)
        result_text.grid(row=7, column=1, padx=5, pady=5)
        scrollbar.grid(row=7, column=2, sticky="ns")
        scrollbar_x.grid(row=8, column=1, sticky="we")
        send_button.grid(row=5, column=1, padx=5, pady=5, sticky="w")

        # suppression des widgets des "status"
        status_label.grid_remove()
        status_text_critical.grid_remove()
        status_text_warning.grid_remove()
        status_text_ok.grid_remove()
        status_text_unknown.grid_remove()
        
        # modification du texte du bouton "show_button"
        show_button.config(text="Cacher")

        # création d'une barre de menu
        create_menu()

# Fonction  pour la création d'un menu
def create_menu():

    # Création d'un menu
    menu_bar = tk.Menu(root)
    root.config(menu=menu_bar)

    # Création d'un menu "Paramètres"
    settings_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Paramètres", menu=settings_menu)
    settings_menu.add_command(label="Nouveau Token", command=connect)
    settings_menu.add_command(label="Sauvegarder", command=save_config)
    settings_menu.add_command(label="Charger", command=load_config)
    settings_menu.add_command(label="Réduire", command=hide_show)
    settings_menu.add_command(label="Quitter", command=root.destroy)

    # creation d'un menu "Aide"
    help_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Aide", menu=help_menu)
    help_menu.add_command(label="A propos", command=about)

# fonction pour la suppression du menu
def delete_menu():
    menu_bar = tk.Menu(root)
    root.config(menu=menu_bar)

create_menu()

# Création de la zone de saisie pour l'url de l'API
url_label = tk.Label(root, text="URL :")
url_label.grid(row=0, column=0, padx=5, pady=5)
url_entry = tk.Entry(root, width=50)
url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
url_entry.insert(0, config_splunk_url)

# Création de la zone de saisie pour le nom d'utilisateur
username_label = tk.Label(root, text="Nom d'utilisateur :")
username_label.grid(row=1, column=0, padx=5, pady=5)
username_entry = tk.Entry(root)
username_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
username_entry.insert(0, config_splunk_username)

# Création de la zone de saisie pour le mot de passe
password_label = tk.Label(root, text="Mot de passe :")
password_label.grid(row=2, column=0, padx=5, pady=5)
password_entry = tk.Entry(root, show="*")
password_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
password_entry.insert(0, "tototiti")

# Création de la zone de saisie pour la requête
query_label = tk.Label(root, text="Requête :")
query_label.grid(row=3, column=0, padx=5, pady=5)
query_entry = tk.Entry(root, width=150, )
query_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")
query_entry.insert(0, config_splunk_query)

# Création d'une liste deroulante pour choisir l'intervalle de temps en secondes entre chaque requête
# l'utilisateur fait son choix dans la liste deroulante et le libellé du choix est affiché en minutes qui sont converties en secondes
# les choix possibles sont 1, 2, 5, 10, 15, 30, 60 minutes
# la valeur par défaut est 5 minutes
# la valeur est stockée dans la variable interval_var
interval_label = tk.Label(root, text="Inerval (min.) :")
interval_label.grid(row=4, column=0, padx=5, pady=5)
interval_var = tk.StringVar(root)
interval_var.set(config_interval)
interval_menu = tk.OptionMenu(root, interval_var, "1", "2", "5", "10", "15", "30", "60")
interval_menu.grid(row=4, column=1, padx=5, pady=5, sticky="w")
interval = int(interval_var.get()) * 60

# création d'un bouton pour afficher la fenêtre secondaire
show_button = tk.Button(root, text="Cacher", command=hide_show)
show_button.grid(row=5, column=2, padx=5, pady=5, sticky="w")

# Création du bouton pour envoyer la requête
send_button = tk.Button(root, text="Envoyer", command=send_query)
send_button.grid(row=5, column=1, padx=5, pady=5, sticky="w")

# creation d'une zone de texte pour afficher les statuts
status_label = tk.Label(root)
status_text_critical = tk.Text(root, height=1, width=20)
status_text_critical.configure(background="red", selectbackground="blue", selectforeground="white", foreground="white")
status_text_warning = tk.Text(root, height=1, width=20)
status_text_warning.configure(background="yellow", selectbackground="blue", selectforeground="white")
status_text_ok = tk.Text(root, height=1, width=20)
status_text_ok.configure(background="green", selectbackground="blue", selectforeground="white", foreground="white")
status_text_unknown = tk.Text(root, height=1, width=20)
status_text_unknown.configure(background="grey", selectbackground="blue", selectforeground="white")

# Création de la zone de sortie pour afficher les résultats de la requête
result_label = tk.Label(root, text="Résultat :")
result_label.grid(row=7, column=0, padx=5, pady=5)
result_text = tk.Text(root, height=20, width=150)
result_text.grid(row=7, column=1, padx=5, pady=5)
result_text.config(wrap="none")

# Création de la barre de défilement pour la zone de sortie
scrollbar = tk.Scrollbar(root)
scrollbar.grid(row=7, column=2, sticky="ns")
result_text.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=result_text.yview)

# Création d'une barre de défilement horizontale pour la zone texte de sortie des résultats et désactive le retour à la ligne automatique
scrollbar_x = tk.Scrollbar(root, orient="horizontal")
scrollbar_x.grid(row=8, column=1, sticky="we")
result_text.config(xscrollcommand=scrollbar_x.set)
scrollbar_x.config(command=result_text.xview)


# création d'un thread pour lancer la fonction "check_hide" en parallèle
thread = threading.Thread(target=check_hide)
thread.start()

load_config()

# Lancement de la boucle d'événements Tkinter
root.mainloop()
