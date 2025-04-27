import requests
import pandas as pd
import os
import time
from datetime import datetime, timezone, timedelta

CSV_FILENAME = 'mlb_2025_schedule.csv'

def fetch_mlb_schedule_season():
    url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2025"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching MLB schedule: {e}")
        return None

    dates = data.get('dates', [])
    print(f"Found {len(dates)} dates scheduled!")

    all_games = []
    for date_entry in dates:
        date = date_entry.get('date')
        games = date_entry.get('games', [])

        for game in games:
            try:
                game_id = game['gamePk']
                game_time = game['gameDate']
                away_team = game['teams']['away']['team']['name']
                home_team = game['teams']['home']['team']['name']
                venue = game.get('venue', {}).get('name', 'Unknown')
                status = game.get('status', {}).get('detailedState', 'Scheduled')
                game_type = game.get('gameType', 'Unknown')

                all_games.append({
                    'game_id': game_id,
                    'date': date,
                    'game_time': game_time,
                    'team_away': away_team,
                    'team_home': home_team,
                    'venue': venue,
                    'game_type': game_type,
                    'status': status,
                    'home_score': None,
                    'away_score': None
                })
            except Exception as e:
                print(f"⚠️ Error parsing a game info: {e}")

    df = pd.DataFrame(all_games)
    df.to_csv(CSV_FILENAME, index=False)
    print(f"Saved {len(df)} games to {CSV_FILENAME}")
    return df

def get_final_score(game_id):
    box_url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    try:
        r = requests.get(box_url)
        r.raise_for_status()
        box_data = r.json()

        home_runs = box_data['teams']['home']['teamStats']['batting']['runs']
        away_runs = box_data['teams']['away']['teamStats']['batting']['runs']

        return home_runs, away_runs
    except Exception as e:
        print(f"Error pulling boxscore for game {game_id}: {e}")
        return None, None

def get_live_score(game_id):
    live_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
    try:
        r = requests.get(live_url)
        r.raise_for_status()
        live_data = r.json()

        linescore = live_data.get('liveData', {}).get('linescore', {}).get('teams', {})
        if linescore:
            home_runs = linescore['home'].get('runs')
            away_runs = linescore['away'].get('runs')
            return home_runs, away_runs

        return None, None
    except Exception as e:
        print(f"Error pulling live feed for game {game_id}: {e}")
        return None, None

def live_update_scores(df):
    print("\nEntering live updating mode...")

    while True:
        now_utc = datetime.now(timezone.utc)
        updated = False

        print(f"\nChecking MLB data at {now_utc.isoformat()} UTC")

        for idx, row in df.iterrows():
            try:
                scheduled_time = datetime.fromisoformat(row['game_time'].replace('Z', '+00:00'))
            except Exception:
                continue

            # ignore games scheduled in the far future
            if now_utc < (scheduled_time - timedelta(hours=1)):
                continue

            game_id = int(row['game_id'])

            try:
                status_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
                r_status = requests.get(status_url)
                r_status.raise_for_status()
                game_data = r_status.json()

                current_status = game_data['gameData']['status'].get('detailedState', row['status'])
                df.at[idx, 'status'] = current_status

                if current_status in ['Final', 'Game Over', 'Completed Early', 'Completed Early: Rain']:
                    home_score, away_score = get_final_score(game_id)
                else:
                    home_score, away_score = get_live_score(game_id)

                if home_score is not None and away_score is not None:
                    df.at[idx, 'home_score'] = home_score
                    df.at[idx, 'away_score'] = away_score

                    print(f"🏟️ {row['team_away']} {away_score} - {row['team_home']} {home_score} ({current_status})")
                    updated = True
                else:
                    print(f"⚠️ No scores available yet for {row['team_away']} @ {row['team_home']} ({current_status})")

            except Exception as e:
                print(f"Error updating game {row['team_away']} at {row['team_home']}: {e}")

        if updated:
            df.to_csv(CSV_FILENAME, index=False)
            print("CSV updated and saved.")
        else:
            print("No active changes, waiting...")

        time.sleep(60)

# === MAIN ENTRY POINT ===
if __name__ == '__main__':
    if os.path.exists(CSV_FILENAME):
        print(f"Loading existing {CSV_FILENAME}")
        df = pd.read_csv(CSV_FILENAME, dtype=str)
    else:
        print(f"Creating schedule file...")
        df = fetch_mlb_schedule_season()

    if df is not None:
        live_update_scores(df)