"""Held-out OOP tasks for the Class Modeler, written independently of the
tuning examples (library / bank / shop / university) and phrased differently
on purpose. Each case lists what a person solving the exercise would produce;
the modeler is scored against it, not tuned to any one of them.

Expectation keys (all optional):
- classes: must be classes
- not_classes: must NOT be classes (usually attributes or the system itself)
- attributes: {Class: [attribute names]}
- methods: {Class: [method names]}
- inherits: [(child, parent)]
- links: [(A, B)] - some relationship between A and B in either direction
- multiplicity: [(source, target, target multiplicity)]
- enums: {EnumName: [LITERALS]}
"""

CASES = [
    {
        "name": "hospital",
        "text": (
            "Design a hospital management system. A patient has a name, a date of birth and a blood group. "
            "A doctor has a name and a specialization. A doctor can examine patients and prescribe medicines. "
            "Each appointment has a date and a time. A patient can book an appointment with a doctor. "
            "A nurse can update the medical record of a patient. A medicine has a name and a dosage."
        ),
        "classes": ["Patient", "Doctor", "Appointment", "Nurse", "Medicine"],
        "not_classes": ["DateOfBirth", "BloodGroup", "Specialization", "Dosage", "System"],
        "attributes": {"Patient": ["name", "dateOfBirth", "bloodGroup"], "Medicine": ["name", "dosage"]},
        "methods": {"Doctor": ["examinePatient", "prescribeMedicine"], "Patient": ["bookAppointment"]},
        "links": [("Doctor", "Patient"), ("Doctor", "Medicine")],
    },
    {
        "name": "parking",
        "text": (
            "A parking lot has several floors. Each floor contains many parking spots. A parking spot can be free or occupied. "
            "A vehicle has a license plate and a color. Cars, motorcycles and trucks are vehicles. "
            "A ticket records the entry time and the exit time. The attendant issues a ticket to each vehicle. "
            "The system calculates the fee for each ticket."
        ),
        "classes": ["ParkingLot", "Floor", "ParkingSpot", "Vehicle", "Car", "Motorcycle", "Truck", "Ticket", "Attendant"],
        "not_classes": ["LicensePlate", "Color", "EntryTime", "Fee", "System"],
        "attributes": {"Vehicle": ["licensePlate", "color"], "Ticket": ["entryTime", "exitTime", "fee"]},
        "methods": {"Attendant": ["issueTicket"], "Ticket": ["calculateFee"]},
        "inherits": [("Car", "Vehicle"), ("Motorcycle", "Vehicle"), ("Truck", "Vehicle")],
        "links": [("ParkingLot", "Floor"), ("Floor", "ParkingSpot")],
        "enums": {"ParkingSpotStatus": ["FREE", "OCCUPIED"]},
    },
    {
        "name": "restaurant",
        "text": (
            "In a restaurant, a waiter takes orders from customers. An order consists of one or more order items. "
            "Each order item has a quantity and a note. A menu item has a name, a description and a price. "
            "The chef prepares the order. A customer pays the bill. A bill has a total amount and a tip."
        ),
        "classes": ["Waiter", "Order", "OrderItem", "MenuItem", "Chef", "Customer", "Bill"],
        "not_classes": ["Quantity", "Price", "TotalAmount", "Tip"],
        "attributes": {"MenuItem": ["name", "description", "price"], "Bill": ["totalAmount", "tip"]},
        "methods": {"Waiter": ["takeOrder"], "Chef": ["prepareOrder"], "Customer": ["payBill"]},
        "multiplicity": [("Order", "OrderItem", "1..*")],
    },
    {
        "name": "airline",
        "text": (
            "An airline operates many flights. A flight has a flight number, a departure time and an arrival time. "
            "Each flight is assigned to exactly one aircraft. An aircraft has a model and a capacity. "
            "A passenger can reserve a seat on a flight. A passenger can cancel a reservation. "
            "A reservation has a booking date and a seat number. The status of a reservation can be confirmed, cancelled or waitlisted."
        ),
        "classes": ["Airline", "Flight", "Aircraft", "Passenger", "Reservation"],
        "not_classes": ["FlightNumber", "DepartureTime", "Capacity", "SeatNumber"],
        "attributes": {"Flight": ["flightNumber", "departureTime", "arrivalTime"], "Aircraft": ["model", "capacity"]},
        "methods": {"Passenger": ["cancelReservation"]},
        "multiplicity": [("Flight", "Aircraft", "1")],
        "links": [("Airline", "Flight")],
        "enums": {"ReservationStatus": ["CONFIRMED", "CANCELLED", "WAITLISTED"]},
    },
    {
        "name": "school-grading",
        "text": (
            "A school has many classrooms. A teacher is an employee. An employee has an employee id and a salary. "
            "A teacher can assign homework to students. A student submits homework. "
            "Homework has a title and a due date. A teacher grades the homework."
        ),
        "classes": ["School", "Classroom", "Teacher", "Employee", "Student", "Homework"],
        "not_classes": ["EmployeeId", "Salary", "Title", "DueDate"],
        "attributes": {"Homework": ["title", "dueDate"], "Employee": ["employeeId", "salary"]},
        "methods": {"Student": ["submitHomework"], "Teacher": ["gradeHomework"]},
        "inherits": [("Teacher", "Employee")],
    },
    {
        "name": "social-media",
        "text": (
            "Users can create posts. A post has a caption, an image and a timestamp. Users can like and comment on posts. "
            "A comment has a text and a date. A user can follow other users. A user has a username, an email and a bio."
        ),
        "classes": ["User", "Post", "Comment"],
        "not_classes": ["Caption", "Timestamp", "Username", "Bio"],
        "attributes": {"Post": ["caption", "image", "timestamp"], "User": ["username", "email", "bio"]},
        "methods": {"User": ["createPost", "likePost", "followUser"]},
        "links": [("User", "Post")],
    },
    {
        "name": "hotel",
        "text": (
            "The hotel has 200 rooms. Every room has a room number, a type and a nightly rate. "
            "A room is either available, occupied or under maintenance. "
            "Guests make bookings. A booking has a check-in date and a check-out date. "
            "The receptionist checks in guests and checks out guests. A guest may cancel a booking."
        ),
        "classes": ["Hotel", "Room", "Guest", "Booking", "Receptionist"],
        "not_classes": ["RoomNumber", "NightlyRate", "CheckInDate"],
        "attributes": {"Room": ["roomNumber", "type", "nightlyRate"], "Booking": ["checkInDate", "checkOutDate"]},
        "methods": {"Guest": ["makeBooking", "cancelBooking"]},
        "multiplicity": [("Hotel", "Room", "200")],
    },
    {
        "name": "inventory-passive",
        "text": (
            "Products are supplied by suppliers. A supplier has a company name and a contact number. "
            "Each product belongs to one category. A category has a name. "
            "Stock is updated by the warehouse manager. The warehouse manager can generate reports."
        ),
        "classes": ["Product", "Supplier", "Category", "WarehouseManager", "Report"],
        "not_classes": ["CompanyName", "ContactNumber"],
        "attributes": {"Supplier": ["companyName", "contactNumber"], "Category": ["name"]},
        "methods": {"Supplier": ["supplyProduct"], "WarehouseManager": ["generateReport"]},
        "multiplicity": [("Product", "Category", "1")],
    },
    {
        "name": "vehicle-rental-bulleted",
        "text": (
            "- Customers rent vehicles.\n"
            "- A rental has a start date, an end date and a total cost.\n"
            "- A vehicle has a registration number and a daily rate.\n"
            "- Each rental is for exactly one vehicle.\n"
            "- A customer can have at most 3 active rentals.\n"
            "- Staff can register new vehicles."
        ),
        "classes": ["Customer", "Rental", "Vehicle", "Staff"],
        "not_classes": ["StartDate", "TotalCost", "RegistrationNumber", "DailyRate"],
        "attributes": {"Rental": ["startDate", "endDate", "totalCost"], "Vehicle": ["registrationNumber", "dailyRate"]},
        "methods": {"Customer": ["rentVehicle"], "Staff": ["registerVehicle"]},
    },
    {
        "name": "zoo-inheritance-variants",
        "text": (
            "A zoo keeps many animals. Every animal has a name and an age. "
            "Mammals, birds and reptiles are kinds of animals. A bird has a wingspan. "
            "A zookeeper feeds animals. A zookeeper has a name and a shift."
        ),
        "classes": ["Zoo", "Animal", "Mammal", "Bird", "Reptile", "Zookeeper"],
        "not_classes": ["Wingspan", "Shift", "Age"],
        "attributes": {"Animal": ["name", "age"], "Bird": ["wingspan"]},
        "methods": {"Zookeeper": ["feedAnimal"]},
        "inherits": [("Mammal", "Animal"), ("Bird", "Animal"), ("Reptile", "Animal")],
    },
    {
        "name": "event-management",
        "text": (
            "An organizer creates events. An event has a title, a venue and a start time. "
            "Attendees register for events. An event can have up to 500 attendees. "
            "Each attendee receives a ticket. A ticket has a ticket code and a price."
        ),
        "classes": ["Organizer", "Event", "Attendee", "Ticket"],
        "not_classes": ["Venue", "StartTime", "TicketCode", "Price"],
        "attributes": {"Event": ["title", "venue", "startTime"], "Ticket": ["ticketCode", "price"]},
        "methods": {"Organizer": ["createEvent"], "Attendee": ["registerEvent", "receiveTicket"]},
        "multiplicity": [("Event", "Attendee", "0..500")],
    },
    {
        "name": "atm",
        "text": (
            "An ATM is used by account holders. An account holder inserts a card and enters a PIN. "
            "A card has a card number and an expiry date. The ATM dispenses cash. "
            "An account holder can check the balance and transfer funds to another account. "
            "An account has an account number and a balance."
        ),
        "classes": ["Atm", "AccountHolder", "Card", "Account"],
        "not_classes": ["Pin", "CardNumber", "Cash", "Balance"],
        "attributes": {"Card": ["cardNumber", "expiryDate"], "Account": ["accountNumber", "balance"]},
        "methods": {"AccountHolder": ["insertCard", "enterPin", "checkBalance"]},
    },
]
