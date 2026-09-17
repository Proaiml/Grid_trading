"""
Grid Trading Bot - Interactive Simulator & Backtest
Demonstrates the exact grid trading algorithm created by İlhan Koçaslan in main.py
without needing live Binance API keys or risking real capital.
"""

import math
import random
import matplotlib.pyplot as plt

def run_simulation():
    print("=" * 70)
    print("             GRID TRADING BOT - STRATEGY SIMULATOR")
    print("                 Strategy Logic by İlhan Koçaslan")
    print("=" * 70)

    # 1. Strategy Parameters (Same structure as main.py)
    Asset = "MATICUSDT"
    Price_Low = 1.42
    Price_High = 1.70
    Grid_Number = 4
    Balance = 60.0
    
    Grid_Area = Grid_Number + 1
    Sector_Balance = Balance / Grid_Area
    Grid_balance = (Price_High - Price_Low) / Grid_Area

    # Build sectors exactly as main.py does
    all_sector = []
    dead_zone = [0.0, Price_Low, "$"]
    higher_zone = [Price_High, 9999999.0, "$"]
    all_sector.append({"dead_zone": dead_zone})
    all_sector.append({"higher_zone": higher_zone})

    for lo in range(1, Grid_Area + 1):
        if lo == 1:
            Lgrid = Price_Low
            Hgrid = Lgrid + Grid_balance
        else:
            Lgrid = Grid_balance * (lo - 1) + Price_Low
            Hgrid = Lgrid + Grid_balance

        name = f"sector{lo}"
        # [Lgrid, Hgrid, status ("$" or "A"), allocated_amount]
        all_sector.append({name: [Lgrid, Hgrid, "$", Sector_Balance]})

    print("\n[*] Grid Configuration:")
    print(f"    - Asset:          {Asset}")
    print(f"    - Low Boundary:   ${Price_Low:.4f} (Dead Zone below this)")
    print(f"    - High Boundary:  ${Price_High:.4f} (Higher Zone above this)")
    print(f"    - Total Grids:    {Grid_Number} (Area count: {Grid_Area})")
    print(f"    - Grid Step Size: ${Grid_balance:.4f}")
    print(f"    - Initial Capital:${Balance:.2f} (Per sector: ${Sector_Balance:.2f})")
    print("\n[*] Grid Levels:")
    for s in all_sector:
        for k, v in s.items():
            print(f"    {k:<12}: ${v[0]:.4f} - ${v[1]:.4f}  [Initial State: {v[2]}]")

    # Helper functions matching main.py logic
    def find_section(current_price):
        for sfo in all_sector:
            for sfoo, sfooval in sfo.items():
                if sfooval[0] <= current_price < sfooval[1]:
                    return sfoo
        return "higher_zone"

    def get_sector_state(sec_name):
        for s in all_sector:
            if sec_name in s:
                return s[sec_name][2]
        return "$"

    def set_sector_state(sec_name, direction, amount):
        for s in all_sector:
            if sec_name in s:
                s[sec_name][2] = direction
                s[sec_name][3] = amount

    # Generate synthetic oscillatory market price series simulating ranging/sideways market
    print("\n[+] Generating market price oscillation data...")
    steps = 120
    prices = []
    base_price = (Price_Low + Price_High) / 2.0
    current_p = base_price

    random.seed(42)
    for t in range(steps):
        # Sine wave oscillation with random noise to simulate natural crypto volatility
        noise = random.uniform(-0.015, 0.015)
        oscillation = math.sin(t / 8.0) * ((Price_High - Price_Low) * 0.45)
        current_p = base_price + oscillation + noise
        current_p = max(Price_Low * 0.98, min(Price_High * 1.02, current_p))
        prices.append(current_p)

    # 2. Run Trading Simulation Loop
    print("\n" + "=" * 70)
    print("                     EXECUTING TRADING LOGIC")
    print("=" * 70)
    print(f"{'Step':<6} {'Price':<10} {'Previous Sec':<14} {'Current Sec':<14} {'Action Taken':<22}")
    print("-" * 70)

    total_trade = 0
    total_profit = 0.0
    cash_balance = Balance
    trade_history = []
    buy_points = []
    sell_points = []

    last_sec = find_section(prices[0])

    for i, p in enumerate(prices):
        new_sec = find_section(p)
        action_text = "Holding"

        if last_sec != new_sec:
            # Transition occurred! Check direction and sector states
            if new_sec == "higher_zone":
                state = get_sector_state(last_sec)
                if state == "A":
                    # Sell held asset at profit
                    total_trade += 1
                    profit_per_trade = Sector_Balance * (Grid_balance / Price_Low)
                    total_profit += profit_per_trade
                    set_sector_state(last_sec, "$", Sector_Balance)
                    sell_points.append((i, p))
                    action_text = f"SELL (Higher Zone) +${profit_per_trade:.2f}"

            elif new_sec == "dead_zone":
                state = get_sector_state(last_sec)
                if state == "$":
                    # Buy on the lowest dip
                    set_sector_state(last_sec, "A", Sector_Balance / p)
                    buy_points.append((i, p))
                    action_text = f"BUY (Dead Zone Dip)"

            else:
                # Inter-grid sector transition
                new_num = int(new_sec.replace("sector", ""))
                last_num = int(last_sec.replace("sector", "")) if "sector" in last_sec else 1

                if new_num > last_num:
                    # Price moved up -> Sell to take profit
                    state = get_sector_state(last_sec)
                    if state == "A":
                        total_trade += 1
                        profit_per_trade = Sector_Balance * (Grid_balance / p)
                        total_profit += profit_per_trade
                        set_sector_state(last_sec, "$", Sector_Balance)
                        sell_points.append((i, p))
                        action_text = f"SELL Sector {last_num} (+${profit_per_trade:.2f})"
                else:
                    # Price moved down -> Buy on discount
                    state = get_sector_state(last_sec)
                    if state == "$":
                        set_sector_state(last_sec, "A", Sector_Balance / p)
                        buy_points.append((i, p))
                        action_text = f"BUY Sector {last_num}"

            print(f"#{i:<5} ${p:<9.4f} {last_sec:<14} {new_sec:<14} {action_text:<22}")
            trade_history.append((i, p, action_text))
            last_sec = new_sec

    # 3. Summary Performance Report
    print("\n" + "=" * 50)
    print("              SIMULATION SUMMARY")
    print("=" * 50)
    print(f"Total Price Steps Simulated: {steps}")
    print(f"Total Round-Trip Trades:     {total_trade}")
    print(f"Total Strategy Profit:       ${total_profit:.2f}")
    print(f"Net Final Portfolio:         ${Balance + total_profit:.2f}")
    roi = (total_profit / Balance) * 100
    print(f"Simulated Return (ROI):      %{roi:.2f}")
    print("=" * 50)

    # 4. Visualization Plot
    try:
        plt.figure(figsize=(12, 6))
        plt.plot(prices, label=f"{Asset} Simulated Price", color="#2563eb", linewidth=1.5)

        # Plot horizontal grid boundaries
        plt.axhline(Price_Low, color="#ef4444", linestyle="--", alpha=0.7, label=f"Price Low (${Price_Low})")
        plt.axhline(Price_High, color="#10b981", linestyle="--", alpha=0.7, label=f"Price High (${Price_High})")

        # Plot interior grid lines
        for s in all_sector:
            for k, v in s.items():
                if "sector" in k:
                    plt.axhline(v[0], color="#94a3b8", linestyle=":", alpha=0.5)

        # Plot buy/sell markers
        if buy_points:
            bx, by = zip(*buy_points)
            plt.scatter(bx, by, color="#10b981", marker="^", s=100, zorder=5, label="BUY Signal")
        if sell_points:
            sx, sy = zip(*sell_points)
            plt.scatter(sx, sy, color="#ef4444", marker="v", s=100, zorder=5, label="SELL Signal")

        plt.title(f"Grid Trading Strategy Simulation ({Asset}) - Trades: {total_trade} | Profit: +${total_profit:.2f}")
        plt.xlabel("Timeline Steps")
        plt.ylabel("Asset Price ($)")
        plt.legend(loc="upper right")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        print("\n[+] Displaying simulation graph...")
        plt.show()
    except Exception as e:
        print(f"Note: Could not open plot window: {e}")

if __name__ == "__main__":
    run_simulation()
