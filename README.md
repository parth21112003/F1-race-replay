# F1 Race Replay

F1 Race Replay is an interactive application designed to visualize and replay Formula 1 races and qualifying sessions. Built using Python, PySide6, and the FastF1 library, this tool provides rich telemetry insights, track visualizations, and an arcade-style replay experience.

## Features

- **Race & Qualifying Replays**: Visualize sessions (Race, Sprint, Qualifying) with accurate telemetry.
- **Graphical User Interface**: Launch an intuitive GUI to select the year, round, and session type.
- **Command-Line Interface**: Run replays directly from the terminal with various configuration flags.
- **Telemetry Insights**: Dive deep into driver telemetry, tyre degradation, and track statuses.
- **Arcade Viewer**: Enjoy a stylized, arcade-like replay with HUD and track layout rotation options.

## Requirements

Ensure you have Python installed. The required dependencies are listed in `requirements.txt`.
You can install them via:
```bash
pip install -r requirements.txt
```

## Usage

### Running the GUI
To launch the graphical race selection window, simply run:
```bash
python main.py
```

### Running the CLI
You can launch replays directly using command-line arguments:
```bash
python main.py --cli
```

#### Example CLI Flags:
- `--year 2023` : Specify the F1 season year.
- `--round 12` : Specify the round number.
- `--viewer` : Launch directly into the replay viewer.
- `--qualifying` or `--sprint` or `--sprint-qualifying` : Select session types instead of a Race.
- `--no-hud` : Hide the HUD during the replay.
- `--list-rounds` / `--list-sprints` : List available rounds and sprints for a given year.

## Architecture & Data

- Uses **FastF1** for fetching official F1 telemetry and timing data.
- Includes a sophisticated tyre degradation model and real-time event detector.
- Results and telemetry data are cached locally (in `.fastf1-cache`) to speed up subsequent loads.

## License

This project is open-source. Please see the license file for more details.
