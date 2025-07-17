import json
import math 
import asyncio
from datetime import datetime
from pyscript import document, window
from js import alert

class User:
    #Class for user data
    def __init__(self):
        self.name = ""
        self.residence = ""
        self.StrageKey = 'user_profile'

    def IsRegistered(self):
        #Check if user information is registered
        return bool(self.name and self.residence)

    def save(self, name, residence):
        #Save user data
        self.name = name
        self.residence = residence
        profile = {"name": self.name, "residence": self.residence}
        window.localStorage.setItem(self.StrageKey, json.dumps(profile)) #save to localStorage
    
    def load(self):
        #load user data
        ProfileStar = window.localStorage.getItem(self.StrageKey)
        if ProfileStar:
            profile = json.loads(ProfileStar)
            self.name = profile.get("name", "")
            self.residence = profile.get("residence", "")
            return True
        return False

class CFPApp:
    #Class CFP Calculation
    DBPath = './Database.json'
    EmissionPerKM = 0.0002
    TreePerYear = 14
    StrageKey = 'AllRecords'

    def __init__(self):
        self.user = User()
        self.FoodDatabase = {}
        self.DailyInput = []
        self.AllRecords = []

    # Loading
    def ShowLoading(self, IsVisible):
        DisplayStyle = "flex" if IsVisible else "none"
        document.getElementById("loading").style.display = DisplayStyle

    def UpdateUI(self):
        #update UI
        if self.user.IsRegistered():
            document.getElementById("profile-title").innerText = f"HELLO, {self.user.name}!"
            document.getElementById("profile-display").innerText = f"Location: {self.user.residence}"
            document.getElementById("profile-setup").style.display = "none"
            document.getElementById("main-app").style.display = "block"
            document.getElementById("dashboard-section").style.display = "block"
            self.UpdateDashboard()
        else:
            document.getElementById("profile-setup").style.display = "block"
            document.getElementById("main-app").style.display = "none"
            document.getElementById("dashboard-section").style.display = "none"

    # User data
    def SaveUserData(self, event):
        name = document.getElementById("user-name").value
        residence = document.getElementById("user-residence").value
        if not name or not residence:
            alert("Please enter your name and location.")
            return
        
        self.user.save(name, residence)
        alert("Success!")
        self.UpdateUI()

    # distance calculation
    @staticmethod
    async def GetCoords(PlaceName):
        query = PlaceName.replace(" ", "+")
        url = f"https://nominatim.openstreetmap.org/search?q={query}&format=jsonv2&limit=1" # API for calculate distance
        try:
            response = await window.fetch(url, method="GET")
            if not response.ok: return None
            data = (await response.json()).to_py()
            return (float(data[0]['lat']), float(data[0]['lon'])) if data else None
        except Exception: return None

    @staticmethod
    def DistanceCalculation(coords1, coords2):
        R = 6371 
        lat1, lon1 = map(math.radians, coords1)
        lat2, lon2 = map(math.radians, coords2)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    async def GetDistance(self, origin, destination):
        Coords1Task = self.GetCoords(origin)
        Coords2Task = self.GetCoords(destination)
        coords1, coords2 = await asyncio.gather(Coords1Task, Coords2Task)
        if coords1 and coords2:
            return self.DistanceCalculation(coords1, coords2)
        alert(f"fail to find location: {origin if not coords1 else ''} {destination if not coords2 else ''}")
        return None

    # --- FoodList ---
    def AddFood(self, event):
        FoodID = document.getElementById("food-item").value
        origin = document.getElementById("origin").value
        if not origin:
            alert("Please enter the origin.")
            return

        self.DailyInput.append({
            "FoodID": FoodID,
            "quantity": float(document.getElementById("quantity").value),
            "unit": document.getElementById("unit").value,
            "origin": origin
        })
        self.UpdateDailyTable()

    def UpdateDailyTable(self):
        TableBody = document.querySelector("#daily-list-table tbody")
        TableBody.innerHTML = ""
        for entry in self.DailyInput:
            FoodInfo = self.FoodDatabase.get(entry['FoodID'], {})
            FoodName = FoodInfo.get('NameEn', 'unknown')
            row = document.createElement("tr")

            #add to table oneby one
            NameCell = document.createElement("td")
            NameCell.textContent = FoodName
            row.appendChild(NameCell)

            QuantityCell = document.createElement("td")
            QuantityCell.textContent = f"{entry['quantity']} {entry['unit']}"
            row.appendChild(QuantityCell)

            OriginCell = document.createElement("td")
            OriginCell.textContent = entry['origin']
            row.appendChild(OriginCell)

            TableBody.appendChild(row)

    # CFP clculation for a day
    async def CalculateDaily(self, event):
        if not self.DailyInput:
            alert("Add food item to the list")
            return

        self.ShowLoading(True)
        SumarryData, totals = [], {"weight": 0, "cfp": 0, "DomesticCFP": 0}

        for entry in self.DailyInput:
            FoodInfo = self.FoodDatabase[entry['FoodID']]
            weight = entry['quantity'] * (FoodInfo['avg_weight_kg'] or 1)
            
            distance = await self.GetDistance(entry['origin'], self.user.residence)
            DomesticDistance = await self.GetDistance(FoodInfo['domestic_origin'], self.user.residence)

            if distance is None or DomesticDistance is None:
                self.ShowLoading(False)
                return

            cfp = weight * distance * self.EmissionPerKM
            DomesticCFP = weight * DomesticDistance * self.EmissionPerKM
            
            SumarryData.append({"name": FoodInfo['NameEn'], "weight": weight, "cfp": cfp, "DomesticCFP": DomesticCFP})
            totals["weight"] += weight
            totals["cfp"] += cfp
            totals["DomesticCFP"] += DomesticCFP

        # Result display and save
        self.ShowSumarryTable(SumarryData, totals)
        self.AllRecords.append({
            "date": datetime.now().strftime('%Y-%m-%d'),
            "total_cfp": totals["cfp"],
        })
        window.localStorage.setItem(self.StrageKey, json.dumps(self.AllRecords))
        
        self.DailyInput = []
        self.UpdateDailyTable()
        self.UpdateDashboard()
        self.ShowLoading(False)

    def ShowSumarryTable(self, data, totals):
        TableBody = document.querySelector("#summary-table tbody")
        TableBody.innerHTML = ""
        for item in data:
            row = document.createElement("tr")

            # add to table one by one
            NameCell = document.createElement("td")
            NameCell.textContent = item['name']
            row.appendChild(NameCell)

            WeightCell = document.createElement("td")
            WeightCell.textContent = f"{item['weight']:.2f}"
            row.appendChild(WeightCell)

            CFPCell = document.createElement("td")
            CFPCell.textContent = f"{item['cfp']:.2f}"
            row.appendChild(CFPCell)

            DomesticCFPCell = document.createElement("td")
            DomesticCFPCell.textContent = f"{item['DomesticCFP']:.2f}"
            row.appendChild(DomesticCFPCell)

            TableBody.appendChild(row)
        
        document.getElementById("total-weight").innerText = f"{totals['weight']:.2f}"
        document.getElementById("total-cfp").innerText = f"{totals['cfp']:.2f}"
        document.getElementById("total-domestic-cfp").innerText = f"{totals['DomesticCFP']:.2f}"
        document.getElementById("summary-section").style.display = "block"

    # Dash board
    def UpdateDashboard(self):
        TotalCFP = sum(r['total_cfp'] for r in self.AllRecords)
        TreesNeed = TotalCFP / self.TreePerYear

        TotalCFPDiv = document.getElementById("dashboard-stats")
        TotalCFPDiv.innerHTML = f"<p><strong>Total CFP:</strong> {TotalCFP:.2f} kg-CO₂</p>"
        
        ForestDiv = document.getElementById("my-forest")
        ForestDiv.textContent = "🌳" * int(TreesNeed) if TreesNeed > 0 else "No forest you need yet."

    async def run(self):
        #Today's date
        document.getElementById("current-date").innerText = f"Date of Today: {datetime.now().strftime('%B %d, %Y')}"

        # Load database
        try:
            response = await window.fetch(self.DBPath)
            self.FoodDatabase = (await response.json()).to_py()
        except Exception as e:
            alert(f"Failed to load database: {e}")
            return

        # Load records
        StrDataForRocal = window.localStorage.getItem(self.StrageKey)
        if StrDataForRocal: self.AllRecords = json.loads(StrDataForRocal)
        
        self.user.load()
        self.UpdateUI()

app = CFPApp()
window.app = app
asyncio.create_task(app.run())