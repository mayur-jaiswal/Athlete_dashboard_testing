from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float
import datetime as dt
from collections import defaultdict

# how initialise the db object, define your model, 
# and create the table. 
class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)

# create the app
app = Flask(__name__)

# configure the SQLite database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///athlete_data.db"

# initialize the app with the extension
db.init_app(app)

class Athlete_Data(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(250), nullable=True)
    activity_type: Mapped[str] = mapped_column(String(100), nullable=True)
    distance: Mapped[float] = mapped_column(Float, nullable=True)
    time: Mapped[str] = mapped_column(String(50), nullable=True)  # Store as HH:MM:SS string
    pace: Mapped[str] = mapped_column(String(50), nullable=True)  # Store as MM:SS per km
    calories: Mapped[float] = mapped_column(Float, nullable=True)
    month_year: Mapped[str] = mapped_column(String(50), nullable=True)  # Store "MM-YYYY"

# Create table schema in the database. Requires application context.
with app.app_context():
    db.create_all()

# helper to extract month-year from date string
def get_month_year(date_str):
    """Extract MM-YYYY from DD-MM-YYYY date string"""
    if date_str:
        parts = date_str.split('-')
        if len(parts) == 3:
            return f"{parts[1]}-{parts[2]}"  # MM-YYYY
    return None

# helper to calculate pace (min/km) from distance and time
def calculate_pace(distance_km, time_str):
    """Calculate pace in MM:SS format from distance and time"""
    if not distance_km or distance_km <= 0 or not time_str:
        return None
    
    try:
        # Parse time string HH:MM:SS or MM:SS
        time_parts = time_str.split(':')
        if len(time_parts) == 3:  # HH:MM:SS
            hours, minutes, seconds = map(int, time_parts)
            total_minutes = hours * 60 + minutes + seconds / 60
        elif len(time_parts) == 2:  # MM:SS
            minutes, seconds = map(int, time_parts)
            total_minutes = minutes + seconds / 60
        else:
            return None
        
        # Calculate pace (minutes per km)
        pace_minutes = total_minutes / distance_km
        pace_mins = int(pace_minutes)
        pace_secs = int((pace_minutes - pace_mins) * 60)
        
        return f"{pace_mins:02d}:{pace_secs:02d}"
    except (ValueError, ZeroDivisionError):
        return None

# helper to recalculate monthly totals
def recalc_monthly_totals():
    with app.app_context():
        result = db.session.execute(db.select(Athlete_Data).order_by(Athlete_Data.date, Athlete_Data.id))
        records = list(result.scalars())
        
        # Group by month_year and calculate totals per month
        monthly_groups = defaultdict(list)
        for r in records:
            if r.month_year:
                monthly_groups[r.month_year].append(r)
        
        db.session.commit()

# Read All Records
with app.app_context():
    result = db.session.execute(db.select(Athlete_Data).order_by(Athlete_Data.date, Athlete_Data.id))
    athlete_data = list(result.scalars())  # Convert to list while session is open
if athlete_data==[]:
    print("No athlete data found in the database.")
else:
    for data in athlete_data: 
        print("Athlete Data:")
        print(f"{data.id} - {data.date} - {data.activity_type} - {data.distance}km - {data.time} - {data.pace} - {data.calories}cal")


@app.route('/')
def home():
    with app.app_context():
        result = db.session.execute(db.select(Athlete_Data).order_by(Athlete_Data.date.desc(), Athlete_Data.id.desc()))
        athlete_data = list(result.scalars())
        
        # Group records by month-year
        monthly_data = defaultdict(list)
        for record in athlete_data:
            if record.month_year:
                monthly_data[record.month_year].append(record)
        
        # Calculate monthly totals (distance and calories)
        monthly_totals = {}
        for month, records in monthly_data.items():
            total_distance = sum((r.distance or 0.0) for r in records)
            total_calories = sum((r.calories or 0.0) for r in records)
            monthly_totals[month] = {
                'distance': total_distance,
                'calories': total_calories
            }
        
        # Sort months in descending order (most recent first)
        sorted_months = sorted(monthly_data.keys(), key=lambda x: dt.datetime.strptime(x, "%m-%Y"), reverse=True)
        
        # Compute overall totals
        total_distance = sum((m.distance or 0.0) for m in athlete_data)
        total_calories = sum((m.calories or 0.0) for m in athlete_data)
    
    return render_template("index.html", 
                         monthly_data=monthly_data, 
                         sorted_months=sorted_months,
                         monthly_totals=monthly_totals,
                         total_distance=total_distance,
                         total_calories=total_calories)

@app.route("/edit", methods=["GET", "POST"])
def edit():
    if request.method == "POST":
        # Update record
        athlete_id = int(request.form.get("id"))
        athlete_record = db.get_or_404(Athlete_Data, athlete_id)
        
        # Handle new date (HTML date input returns YYYY-MM-DD)
        new_date_raw = request.form.get("date")
        if new_date_raw:
            try:
                parsed = dt.datetime.strptime(new_date_raw, "%Y-%m-%d")
                athlete_record.date = parsed.strftime("%d-%m-%Y")
                athlete_record.month_year = parsed.strftime("%m-%Y")
            except (ValueError, TypeError):
                pass

        # Update activity type
        athlete_record.activity_type = request.form.get("activity_type", "Running")
        
        # Update distance
        try:
            athlete_record.distance = float(request.form.get("distance", 0))
        except (ValueError, TypeError):
            athlete_record.distance = 0
        
        # Update time
        athlete_record.time = request.form.get("time", "00:00:00")
        
        # Calculate pace
        athlete_record.pace = calculate_pace(athlete_record.distance, athlete_record.time)
        
        # Update calories
        try:
            athlete_record.calories = float(request.form.get("calories", 0))
        except (ValueError, TypeError):
            athlete_record.calories = 0
        
        db.session.commit()
        recalc_monthly_totals()
        
        return redirect(url_for("home"))
    else:
        # Show edit form
        athlete_id = request.args.get("id")
        athlete_record = db.get_or_404(Athlete_Data, int(athlete_id))
        return render_template("edit.html", data=athlete_record)


@app.route('/delete')
def delete_data():
    # DELETE RECORD
    athlete_id = request.args.get('id')
    athlete_to_delete = db.get_or_404(Athlete_Data, int(athlete_id))
    db.session.delete(athlete_to_delete)
    db.session.commit()

    # Recalculate totals after deletion
    recalc_monthly_totals()
    return redirect(url_for('home'))


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        # Get activity type
        activity_type = request.form.get("activity_type", "Running")
        
        # Get and validate distance
        try:
            distance = float(request.form.get("distance", 0))
        except (ValueError, TypeError):
            distance = 0
        
        # Get time (HH:MM:SS or MM:SS)
        time_str = request.form.get("time", "00:00:00")
        
        # Calculate pace
        pace = calculate_pace(distance, time_str)
        
        # Get calories
        try:
            calories = float(request.form.get("calories", 0))
        except (ValueError, TypeError):
            calories = 0
        
        # Handle optional date input (HTML date returns YYYY-MM-DD)
        date_raw = request.form.get("date")
        if date_raw:
            try:
                parsed = dt.datetime.strptime(date_raw, "%Y-%m-%d")
                date_str = parsed.strftime("%d-%m-%Y")
                month_year_str = parsed.strftime("%m-%Y")
            except (ValueError, TypeError):
                now = dt.datetime.now()
                date_str = now.strftime("%d-%m-%Y")
                month_year_str = now.strftime("%m-%Y")
        else:
            now = dt.datetime.now()
            date_str = now.strftime("%d-%m-%Y")
            month_year_str = now.strftime("%m-%Y")

        with app.app_context():
            new_record = Athlete_Data(
                date=date_str,
                activity_type=activity_type,
                distance=distance,
                time=time_str,
                pace=pace,
                calories=calories,
                month_year=month_year_str
            )
            db.session.add(new_record)
            db.session.commit()

            # Recalculate monthly totals
            recalc_monthly_totals()
        return redirect(url_for('home'))
    else:
        return render_template("add.html")


if __name__ == "__main__":
    # app.run(debug=True)
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=5000)