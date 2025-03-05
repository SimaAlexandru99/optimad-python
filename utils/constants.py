# Acest modul contine toate constantele utilizate in aplicatie.
from typing import Dict, List

# Configurari aplicatie
APP_TITLE = "Optimad"
APP_VERSION = "1.0"
WINDOW_SIZE = "800x600"
MIN_WINDOW_SIZE = (700, 500)

# Configurari intervale de timp
INITIAL_COUNTDOWN = 15  # secunde pana la prima captura
COUNTDOWN_CHECK_INTERVAL = 0.1  # interval verificare numaratoare inversa
THREAD_CLEANUP_TIMEOUT = 0.5  # timp asteptare curatare thread
RETRY_DELAY = 2  # secunde intre reincercari

# Limite validare
MAX_HOURS = 24
MAX_SCREENSHOTS = 60
MIN_INTERVAL_MINUTES = 1  # interval minim intre capturi in minute

# Configurari spatiu disc
MIN_DISK_SPACE = 500 * 1024 * 1024  # 500 MB minim necesar

# Configurari aplicatii suportate
SUPPORTED_APPS: Dict[str, str] = {
    "zoom": "Zoom",
    "teams": "Microsoft Teams",
    "chrome": "Google Chrome"
}

# Configurari captura ecran
SUPPORTED_IMAGE_FORMATS = {'png', 'jpg', 'jpeg'}
DEFAULT_IMAGE_FORMAT = "png"
DEFAULT_JPEG_QUALITY = 95
MAX_CAPTURE_RETRIES = 3

# Configurari teme UI
DEFAULT_THEME = "darkly"
VALID_THEMES: List[str] = [
    "cosmo", "flatly", "journal", "litera", "lumen", "minty",
    "pulse", "sandstone", "united", "yeti", "morph", "simplex",
    "cerculean", "solar", "superhero", "darkly", "cyborg", "vapor"
]

# Configurari fonturi
FONTS = {
    'header': ('Segoe UI', 20, 'bold'),
    'subheader': ('Segoe UI', 12, 'bold'),
    'normal': ('Segoe UI', 10),
    'small': ('Segoe UI', 9),
}

# Configurari culori si stiluri
STYLES = {
    'success': 'success',
    'danger': 'danger',
    'warning': 'warning',
    'info': 'info',
    'primary': 'primary',
}

# Configurari fisiere si directoare
LOG_DIR = "logs"
LOG_FILENAME = "jurnal_erori.txt"
CONFIG_FILENAME = "themeconfig.json"

# Mesaje de eroare
ERROR_MESSAGES = {
    'admin_required': "Aplicatia necesita drepturi de administrator pentru a functiona corect.",
    'disk_space': "Spatiu insuficient pe disc pentru capturi de ecran",
    'invalid_time': "Format de timp invalid. Folositi HH:MM",
    'invalid_hours': "Orele trebuie sa fie intre 1 si {max_hours}",
    'invalid_screenshots': "Capturile de ecran trebuie sa fie intre 1 si {max_screenshots}",
    'invalid_interval': "Intervalul minim intre capturi de ecran este {min_interval} minut(e)",
    'system_date_error': "Nu s-a putut seta data sistemului",
    'capture_failed': "Nu s-a putut realiza captura de ecran dupa mai multe incercari",
    'file_verification': "Verificarea fisierului salvat a esuat",
    'process_stopped': "Proces oprit din cauza esecului capturii de ecran",
}