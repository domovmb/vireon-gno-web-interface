package city

import (
	"std"
	"strconv"
)

// Era represents historical epochs (Doby)
type Era struct {
	Name           string
	StartHeight    int64
	PopulationRate int64 // Nárust populácie za blok
	BuildingCosts  map[string]int64
}

// Building represents infrastructure
type Building struct {
	Name         string
	Level        int64
	BuildedAt    int64
	Owner        std.Address
	Production   map[string]int64 // Produkcia surovín
	StorageLimit int64
}

// Resource types
type Resource struct {
	Wood      int64
	Stone     int64
	Minerals  int64
	Food      int64
	Fish      int64
	Myrian    int64 // Currency
}

// City represents a city with residents and infrastructure
type City struct {
	Name           string
	Mayor          std.Address
	Population     int64
	Resources      Resource
	Buildings      map[string]Building
	Era            string
	CreatedAt      int64
	Coordinates    [2]int64 // Mapa súradnice
	Alliances      map[string]*Alliance
	Contracts      map[string]*CityContract
	LastPopUpdate  int64
}

// Alliance represents agreement between mayors
type Alliance struct {
	CityA       string
	CityB       string
	Mayor1      std.Address
	Mayor2      std.Address
	TradeRatio  map[string]int64 // Výmenný pomer
	CreatedAt   int64
	IsActive    bool
	SharedCoins string // Nová minca z aliancie
}

// CityContract represents trade contract between cities
type CityContract struct {
	ContractID  string
	From        string
	To          string
	Resource    string
	Amount      int64
	Price       int64
	Status      string // pending, active, completed
	CreatedAt   int64
	ExpiresAt   int64
}

// Global state
var (
	cities      = make(map[string]*City)
	alliances   = make(map[string]*Alliance)
	eras        = make(map[string]*Era)
	contracts   = make(map[string]*CityContract)
	currentHeight int64
)

// InitCity initializes a new city with era and coordinates
func InitCity(name string, x int64, y int64, era string, initialMyrian int64) {
	caller := std.GetOrigCaller()
	
	if _, exists := cities[name]; exists {
		panic("City already exists")
	}
	
	city := &City{
		Name:          name,
		Mayor:         caller,
		Population:    100, // Začína s 100 obyvateľmi
		Resources:     Resource{Myrian: initialMyrian, Food: 500, Wood: 300},
		Buildings:     make(map[string]Building),
		Era:           era,
		CreatedAt:     std.GetHeight(),
		Coordinates:   [2]int64{x, y},
		Alliances:     make(map[string]*Alliance),
		Contracts:     make(map[string]*CityContract),
		LastPopUpdate: std.GetHeight(),
	}
	
	cities[name] = city
}

// InitEra initializes a new era with population growth rates
func InitEra(name string, popRate int64) {
	era := &Era{
		Name:           name,
		StartHeight:    std.GetHeight(),
		PopulationRate: popRate,
		BuildingCosts:  make(map[string]int64),
	}
	
	eras[name] = era
}

// BuildBuilding constructs a new building (only mayor)
func BuildBuilding(cityName string, buildingName string, buildingType string) {
	caller := std.GetOrigCaller()
	city, exists := cities[cityName]
	
	if !exists {
		panic("City not found")
	}
	
	if caller != city.Mayor {
		panic("Only mayor can build")
	}
	
	cost := int64(1000) // Base cost
	if city.Resources.Myrian < cost {
		panic("Insufficient Myrian")
	}
	
	city.Resources.Myrian -= cost
	
	building := Building{
		Name:      buildingName,
		Level:     1,
		BuildedAt: std.GetHeight(),
		Owner:     caller,
		Production: make(map[string]int64),
	}
	
	// Nastaví produkciu podľa typu budovy
	switch buildingType {
	case "farm":
		building.Production["food"] = 100
		building.StorageLimit = 5000
	case "lumber":
		building.Production["wood"] = 80
		building.StorageLimit = 4000
	case "mine":
		building.Production["minerals"] = 60
		building.StorageLimit = 3000
	case "harbor":
		building.Production["fish"] = 150
		building.StorageLimit = 6000
	case "shipyard":
		building.Production["ships"] = 10
		building.StorageLimit = 100
	}
	
	city.Buildings[buildingName] = building
	
	// Automaticky zvýši populáciu s modernizáciou
	city.Population += 50
}

// DepositMyrian deposits Myrian to city treasury (generates yields)
func DepositMyrian(cityName string, amount int64) {
	caller := std.GetOrigCaller()
	city, exists := cities[cityName]
	
	if !exists {
		panic("City not found")
	}
	
	if amount <= 0 {
		panic("Amount must be positive")
	}
	
	city.Resources.Myrian += amount
	
	// Výnosy: 5% za blok (automatický príjem)
	yield := amount / 20
	city.Resources.Myrian += yield
}

// WithdrawMyrian withdraws Myrian from city
func WithdrawMyrian(cityName string, amount int64) {
	caller := std.GetOrigCaller()
	city, exists := cities[cityName]
	
	if !exists {
		panic("City not found")
	}
	
	if caller != city.Mayor {
		panic("Only mayor can withdraw")
	}
	
	if city.Resources.Myrian < amount {
		panic("Insufficient Myrian")
	}
	
	city.Resources.Myrian -= amount
}

// UpdatePopulation automatically updates population based on era and buildings
func UpdatePopulation(cityName string) {
	city, exists := cities[cityName]
	if !exists {
		panic("City not found")
	}
	
	era, eraExists := eras[city.Era]
	if !eraExists {
		panic("Era not found")
	}
	
	heightDiff := std.GetHeight() - city.LastPopUpdate
	buildingBonus := int64(len(city.Buildings)) * 10
	
	popGrowth := (era.PopulationRate + buildingBonus) * heightDiff
	city.Population += popGrowth
	city.LastPopUpdate = std.GetHeight()
}

// CreateAlliance creates alliance between two mayors
func CreateAlliance(cityA string, cityB string) {
	caller := std.GetOrigCaller()
	
	cityAObj, existsA := cities[cityA]
	cityBObj, existsB := cities[cityB]
	
	if !existsA || !existsB {
		panic("One or both cities not found")
	}
	
	allianceID := cityA + "-" + cityB
	
	alliance := &Alliance{
		CityA:      cityA,
		CityB:      cityB,
		Mayor1:     caller,
		Mayor2:     cityBObj.Mayor,
		TradeRatio: make(map[string]int64),
		CreatedAt:  std.GetHeight(),
		IsActive:   false,
		SharedCoins: allianceID + "-COIN",
	}
	
	alliances[allianceID] = alliance
}

// ApproveAlliance approves alliance (second mayor)
func ApproveAlliance(allianceID string) {
	caller := std.GetOrigCaller()
	alliance, exists := alliances[allianceID]
	
	if !exists {
		panic("Alliance not found")
	}
	
	if caller != alliance.Mayor2 {
		panic("Only second mayor can approve")
	}
	
	alliance.IsActive = true
}

// TradeWithCity trades resources between allied cities
func TradeWithCity(allianceID string, resource string, amount int64) {
	caller := std.GetOrigCaller()
	alliance, exists := alliances[allianceID]
	
	if !exists {
		panic("Alliance not found")
	}
	
	if !alliance.IsActive {
		panic("Alliance not active")
	}
	
	cityA, _ := cities[alliance.CityA]
	cityB, _ := cities[alliance.CityB]
	
	// Obchod podľa typu zdroja
	if resource == "wood" {
		cityA.Resources.Wood -= amount
		cityB.Resources.Wood += amount
	}
	// Môžu sa pridať ďalšie zdroje...
}

// GetCityInfo returns comprehensive city information
func GetCityInfo(cityName string) string {
	city, exists := cities[cityName]
	if !exists {
		return "City not found"
	}
	
	info := "\n=== " + city.Name + " ===\n"
	info += "Primátor: " + string(city.Mayor) + "\n"
	info += "Doby: " + city.Era + "\n"
	info += "Súradnice: (" + strconv.FormatInt(city.Coordinates[0], 10) + ", " + strconv.FormatInt(city.Coordinates[1], 10) + ")\n"
	info += "Populácia: " + strconv.FormatInt(city.Population, 10) + " obyvateľov\n"
	info += "\nZdroje:\n"
	info += "  Myrian: " + strconv.FormatInt(city.Resources.Myrian, 10) + "\n"
	info += "  Drevo: " + strconv.FormatInt(city.Resources.Wood, 10) + "\n"
	info += "  Kameň: " + strconv.FormatInt(city.Resources.Stone, 10) + "\n"
	info += "  Nerasty: " + strconv.FormatInt(city.Resources.Minerals, 10) + "\n"
	info += "  Potraviny: " + strconv.FormatInt(city.Resources.Food, 10) + "\n"
	info += "  Ryby: " + strconv.FormatInt(city.Resources.Fish, 10) + "\n"
	info += "\nBudovy:\n"
	
	for name, building := range city.Buildings {
		info += "  " + name + " (Úroveň " + strconv.FormatInt(building.Level, 10) + ")\n"
	}
	
	info += "\nAliancie: " + strconv.FormatInt(int64(len(city.Alliances)), 10) + "\n"
	info += "Smluvy: " + strconv.FormatInt(int64(len(city.Contracts)), 10) + "\n"
	
	return info
}