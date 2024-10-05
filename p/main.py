import pygame
import random
import time
import datetime
import asyncio
import os
import platform
import sys
import json  # Importa il modulo json per la serializzazione e deserializzazione
import mimetypes  # Importa mimetypes per aggiungere supporto MIME

# MIME type per i file .wasm
mimetypes.add_type('application/wasm', '.wasm')

if __import__("sys").platform == "emscripten":
    from platform import window

# Controllo per la piattaforma Emscripten (WebAssembly)
if sys.platform == "emscripten":
    print("Running on Emscripten")

# Controllo per la CPU WebAssembly
if 'wasm' in platform.machine():
    print("Running on WebAssembly")

# Le variabili globali per facilitare l'esecuzione
COUNT_DOWN = 3

# Controllo dell'audio
audio_enabled = True
try:
    pygame.mixer.init()
except pygame.error as e:
    print(f"Audio non disponibile: {e}")
    audio_enabled = False


class RecordManager:
    def __init__(self):
        self.records = self.load_records()

    def load_records(self):
        """Carica i record dal localStorage."""
        try:
            records_json = eval("window.localStorage.getItem('puzzle_records')")
            if records_json:
                return json.loads(records_json)  # Deserializza il JSON
        except Exception as e:
            print(f"Errore durante il caricamento dei record: {e}")
        return {}

    def save_record(self, time, user, difficulty):
        """Salva il record se è migliore di quello esistente."""
        try:
            best_record = self.load_best_record(user, difficulty)
            if not best_record or time < best_record['time']:
                self.records[(user, difficulty)] = {'time': time, 'date': datetime.datetime.now().isoformat()}
                eval(f"window.localStorage.setItem('puzzle_records', '{json.dumps(self.records)}')")
                print(f"Record salvato per {user} in difficoltà {difficulty}: {time:.2f}s")
        except Exception as e:
            print(f"Errore durante il salvataggio dei record: {e}")

    def load_best_record(self, user, difficulty):
        """Carica il miglior record salvato per un utente e una difficoltà."""
        return self.records.get((user, difficulty))


def load_image(path):
    """Carica l'immagine dal percorso specificato."""
    if not os.path.exists(path):
        print(f"Immagine non trovata: {path}")
        exit()
    try:
        return pygame.image.load(path)
    except pygame.error as e:
        print(f"Impossibile caricare l'immagine da {path}: {e}")
        exit()


class Button:
    """Classe per gestire i bottoni nel gioco."""
    def __init__(self, image, position):
        self.image = image
        self.rect = self.image.get_rect(topleft=position)

    def draw(self, screen):
        screen.blit(self.image, self.rect.topleft)

    def click(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            return True
        return False


class PuzzleGame:
    """Classe principale per il gioco del puzzle."""
    def __init__(self, image, rows, cols, offset_x=150, offset_y=104):
        self.image = image
        self.rows = rows
        self.cols = cols
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.pieces = []
        self.empty_pos = (cols - 1, rows - 1)
        self.create_pieces()
        self.shuffle_pieces()

    def create_pieces(self):
        piece_width = self.image.get_width() // self.cols
        piece_height = self.image.get_height() // self.rows
        for row in range(self.rows):
            for col in range(self.cols):
                if (row, col) != self.empty_pos:
                    rect = pygame.Rect(col * piece_width, row * piece_height, piece_width, piece_height)
                    piece_image = self.image.subsurface(rect)
                    self.pieces.append({
                        'image': piece_image,
                        'current_pos': (col, row),
                        'correct_pos': (col, row)
                    })

    def shuffle_pieces(self, max_attempts=1000):
        attempts = 0
        while attempts < max_attempts:
            piece_positions = [piece['current_pos'] for piece in self.pieces]
            random.shuffle(piece_positions)
            for i, piece in enumerate(self.pieces):
                piece['current_pos'] = piece_positions[i]

            if self.is_solvable():
                break

            attempts += 1
        else:
            raise RuntimeError("Impossibile generare un puzzle risolvibile dopo molti tentativi.")

    def draw(self, screen):
        piece_width = self.image.get_width() // self.cols
        piece_height = self.image.get_height() // self.rows
        for piece in self.pieces:
            x, y = piece['current_pos']
            screen.blit(piece['image'], (self.offset_x + x * piece_width, self.offset_y + y * piece_height))

    def handle_click(self, position):
        piece_width = self.image.get_width() // self.cols
        piece_height = self.image.get_height() // self.rows
        x = (position[0] - self.offset_x) // piece_width
        y = (position[1] - self.offset_y) // piece_height

        if (x < 0 or x >= self.cols or y < 0 or y >= self.rows or
                (x, y) == self.empty_pos):
            return

        if self.is_adjacent((x, y), self.empty_pos):
            for piece in self.pieces:
                if piece['current_pos'] == (x, y):
                    piece['current_pos'], self.empty_pos = self.empty_pos, piece['current_pos']
                    break

    def is_adjacent(self, pos1, pos2):
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1]) == 1

    def check_win(self):
        return all(piece['current_pos'] == piece['correct_pos'] for piece in self.pieces)

    def is_solvable(self):
        inversions = 0
        one_d_pieces = []

        for row in range(self.rows):
            for col in range(self.cols):
                if (col, row) != self.empty_pos:
                    one_d_pieces.append(
                        self.pieces[row * self.cols + col]['current_pos'][1] * self.cols +
                        self.pieces[row * self.cols + col]['current_pos'][0]
                    )

        for i in range(len(one_d_pieces)):
            for j in range(i + 1, len(one_d_pieces)):
                if one_d_pieces[i] > one_d_pieces[j]:
                    inversions += 1

        if self.cols % 2 == 1:
            return inversions % 2 == 0
        else:
            empty_row_from_bottom = self.rows - self.empty_pos[1]
            return (inversions + empty_row_from_bottom) % 2 == 1


class Puzzle:
    """Classe per gestire il puzzle e l'interfaccia utente."""
    def __init__(self, screen, font, clock, user):
        self.screen = screen
        self.font = font
        self.clock = clock
        self.user = user  # Nome utente loggato
        self.difficulty = None
        self.game_started = False
        self.alpha = 0
        self.best_time = None
        self.best_time_text = ""
        self.elapsed_time = 0
        self.start_time = None
        self.record_manager = RecordManager()
        self.load_assets()

    def load_assets(self):
        """Carica le risorse grafiche del gioco."""
        self.background_image = pygame.transform.scale(load_image("img/background.jpg"), (700, 700))  # Aggiorna percorso
        self.puzzle_images = {
            "easy": pygame.transform.scale(load_image("img/puzzle_image_easy.jpg"), (400, 400)),
            "medium": pygame.transform.scale(load_image("img/puzzle_image_medium.jpg"), (400, 400)),
            "hard": pygame.transform.scale(load_image("img/puzzle_image_hard.jpg"), (400, 400))
        }
        self.start_button = Button(pygame.transform.scale(load_image("img/start_button.png"), (100, 45)), (290, 520))
        self.easy_button = Button(pygame.transform.scale(load_image("img/easy_button.png"), (100, 45)), (180, 550))
        self.medium_button = Button(pygame.transform.scale(load_image("img/medium_button.png"), (100, 45)), (300, 550))
        self.hard_button = Button(pygame.transform.scale(load_image("img/hard_button.png"), (100, 45)), (420, 550))
        self.exit_button = Button(pygame.transform.scale(load_image("img/exit_button.png"), (60, 35)), (510, 570))
        self.back_button = Button(pygame.transform.scale(load_image("img/back_button.png"), (50, 40)), (130, 570))

    def update_best_time_text(self):
        """Aggiorna il testo che mostra il miglior tempo registrato."""
        if self.difficulty:
            self.best_time = self.record_manager.load_best_record(self.user, self.difficulty)
            if self.best_time:
                self.best_time_text = f"Tempo: {self.elapsed_time:.2f}s (Miglior Tempo: {self.best_time['time']:.2f}s)"
            else:
                self.best_time_text = f"Tempo: {self.elapsed_time:.2f}s (Nessun record precedente)"
        else:
            self.best_time_text = ""

    async def run(self):
        """Avvia il ciclo principale del gioco."""
        while True:
            self.screen.blit(self.background_image, (0, 0))
            self.screen.blit(self.font.render(self.best_time_text, True, (255, 255, 255)), (50, 50))  # Mostra il miglior tempo
            self.start_button.draw(self.screen)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if self.start_button.click(event):
                    await self.difficulty_selection()

            pygame.display.flip()

            await asyncio.sleep(0)  # Restituisce il controllo al main loop

    async def difficulty_selection(self):
        """Gestisce la selezione della difficoltà."""
        while not self.game_started:
            self.screen.blit(self.background_image, (0, 0))
            self.easy_button.draw(self.screen)
            self.medium_button.draw(self.screen)
            self.hard_button.draw(self.screen)
            self.exit_button.draw(self.screen)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if self.easy_button.click(event):
                    await self.start_game("easy")

                if self.medium_button.click(event):
                    await self.start_game("medium")

                if self.hard_button.click(event):
                    await self.start_game("hard")

                if self.exit_button.click(event):
                    pygame.quit()
                    exit()

            pygame.display.flip()
            await asyncio.sleep(0)  # Restituisce il controllo al main loop

    async def start_game(self, difficulty):
        """Inizia il gioco con la difficoltà selezionata."""
        self.difficulty = difficulty
        self.elapsed_time = 0
        self.start_time = time.time()
        self.game_started = True

        puzzle_image = self.puzzle_images[difficulty]
        puzzle = PuzzleGame(puzzle_image, 3, 3)

        while self.game_started:
            self.screen.blit(self.background_image, (0, 0))
            puzzle.draw(self.screen)

            if self.check_win(puzzle):
                await self.end_game()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    puzzle.handle_click(event.pos)

            # Calcola e mostra il tempo trascorso
            self.elapsed_time = time.time() - self.start_time
            self.update_best_time_text()

            pygame.display.flip()
            self.clock.tick(30)
            await asyncio.sleep(0)  # Restituisce il controllo al main loop

    def check_win(self, puzzle):
        """Controlla se l'utente ha vinto."""
        if puzzle.check_win():
            self.game_started = False
            return True
        return False

    async def end_game(self):
        """Gestisce la fine del gioco e il salvataggio dei record."""
        # Salva il record se esiste un nuovo miglior tempo
        self.record_manager.save_record(self.elapsed_time, self.user, self.difficulty)

        self.best_time_text = f"Congratulazioni! Hai vinto in {self.elapsed_time:.2f}s!"
        self.screen.fill((0, 0, 0))
        self.screen.blit(self.font.render(self.best_time_text, True, (255, 255, 255)), (200, 200))
        pygame.display.flip()
        await asyncio.sleep(3)  # Aspetta un momento prima di tornare al menu principale
        await self.difficulty_selection()


async def main():
    """Funzione principale per avviare il gioco."""
    pygame.init()
    pygame.display.set_caption("Puzzle Game")
    screen = pygame.display.set_mode((700, 700))
    font = pygame.font.Font(None, 36)
    clock = pygame.time.Clock()

    # Usa un nome utente predefinito per il test
    user = "Player"  # Ottieni il nome utente loggato
    puzzle = Puzzle(screen, font, clock, user)
    await puzzle.run()


if __name__ == "__main__":
    asyncio.run(main())  # Esegui il gioco
