"""Second held-out set, written after the modeler was tuned on oop_eval_cases.py
and never used for tuning. Mixes easy, interface-heavy and deliberately hard
phrasing so the score reflects real generality, not memorised examples."""

BLIND_CASES = [
    {
        "name": "gym",
        "text": (
            "A gym has many members and trainers. A member has a membership number and a join date. "
            "A trainer has a name and a certification. A trainer can create workout plans. "
            "A workout plan contains several exercises. An exercise has a name, sets and repetitions. "
            "Members can attend classes. A class has a schedule and a capacity."
        ),
        "classes": ["Gym", "Member", "Trainer", "WorkoutPlan", "Exercise"],
        "not_classes": ["MembershipNumber", "JoinDate", "Certification", "Capacity"],
        "attributes": {"Member": ["membershipNumber", "joinDate"], "Exercise": ["name", "sets", "repetitions"]},
        "methods": {"Trainer": ["createWorkoutPlan"]},
        "links": [("WorkoutPlan", "Exercise")],
    },
    {
        "name": "notifications-interface",
        "text": (
            "Notifier is an interface with a method send. Email notifiers and SMS notifiers implement Notifier. "
            "An email notifier has a sender address. An SMS notifier has a phone number. "
            "The alert service uses a notifier to notify users."
        ),
        "classes": ["Notifier", "EmailNotifier", "SmsNotifier"],
        "not_classes": ["SenderAddress", "PhoneNumber"],
        "attributes": {"EmailNotifier": ["senderAddress"], "SmsNotifier": ["phoneNumber"]},
        "methods": {"Notifier": ["send"], "EmailNotifier": ["send"], "SmsNotifier": ["send"]},
        "realizes": [("EmailNotifier", "Notifier"), ("SmsNotifier", "Notifier")],
        "interfaces": ["Notifier"],
    },
    {
        "name": "shapes-abstract",
        "text": (
            "Shape is an abstract class. A shape has a color. Triangles, squares and circles are shapes. "
            "A triangle has a base and a height. A square has a side. A circle has a radius. "
            "Every shape can calculate its area and its perimeter."
        ),
        "classes": ["Shape", "Triangle", "Square", "Circle"],
        "not_classes": ["Color", "Radius", "Side"],
        "attributes": {"Shape": ["color"], "Circle": ["radius"], "Square": ["side"]},
        "methods": {"Shape": ["calculateArea", "calculatePerimeter"]},
        "inherits": [("Triangle", "Shape"), ("Square", "Shape"), ("Circle", "Shape")],
        "abstract": ["Shape"],
    },
    {
        "name": "food-delivery",
        "text": (
            "Customers order food from restaurants. A restaurant has a name, an address and a rating. "
            "Each order is delivered by a delivery driver. A delivery driver has a vehicle number. "
            "An order has an order time and a delivery fee. A customer can rate a restaurant. "
            "The status of an order can be placed, preparing, on the way or delivered."
        ),
        "classes": ["Customer", "Restaurant", "Order", "DeliveryDriver"],
        "not_classes": ["VehicleNumber", "DeliveryFee", "Rating"],
        "attributes": {"Restaurant": ["name", "address", "rating"], "Order": ["orderTime", "deliveryFee"]},
        "methods": {"Customer": ["rateRestaurant"], "DeliveryDriver": ["deliverOrder"]},
        "links": [("Customer", "Restaurant")],
    },
    {
        "name": "project-tracker",
        "text": (
            "A project consists of many tasks. A task has a title, a priority and a deadline. "
            "A manager assigns tasks to developers. A developer can update the status of a task. "
            "A developer is an employee. A manager is also an employee. An employee has a name and an email."
        ),
        "classes": ["Project", "Task", "Manager", "Developer", "Employee"],
        "not_classes": ["Priority", "Deadline", "Title"],
        "attributes": {"Task": ["title", "priority", "deadline"], "Employee": ["name", "email"]},
        "methods": {"Manager": ["assignTask"]},
        "inherits": [("Developer", "Employee"), ("Manager", "Employee")],
        "multiplicity": [("Project", "Task", "0..*")],
    },
    {
        "name": "music-streaming",
        "text": (
            "A listener can create playlists. A playlist contains songs. A song has a title, a duration and an artist. "
            "An artist can upload songs. Listeners can follow artists. A premium listener can download songs."
        ),
        "classes": ["Listener", "Playlist", "Song", "Artist"],
        "not_classes": ["Duration", "Title"],
        "attributes": {"Song": ["title", "duration"]},
        "methods": {"Listener": ["createPlaylist", "followArtist"], "Artist": ["uploadSong"]},
        "links": [("Playlist", "Song"), ("Listener", "Artist")],
    },
    {
        "name": "hard-long-sentences",
        "text": (
            "When a patient arrives at the clinic, the receptionist, who also handles billing, registers the patient "
            "and assigns them to an available doctor based on the doctor's specialization and current workload. "
            "Doctors write prescriptions, which pharmacists later fill."
        ),
        "classes": ["Patient", "Receptionist", "Doctor", "Prescription", "Pharmacist"],
        "methods": {"Receptionist": ["registerPatient"], "Doctor": ["writePrescription"], "Pharmacist": ["fillPrescription"]},
        "attributes": {"Doctor": ["specialization", "workload"]},
    },
    {
        "name": "hard-implicit-attributes",
        "text": (
            "Each employee's salary depends on their grade. Employees work in departments headed by a manager. "
            "Payroll runs monthly and produces payslips."
        ),
        "classes": ["Employee", "Department", "Manager", "Payslip"],
        "attributes": {"Employee": ["salary", "grade"]},
        "links": [("Employee", "Department"), ("Department", "Manager")],
    },
    {
        "name": "vending-interface",
        "text": (
            "Define an interface called PaymentMethod that declares pay. Coins and cards implement PaymentMethod. "
            "A vending machine holds many products. A product has a code and a price. "
            "A vending machine can dispense a product."
        ),
        "classes": ["PaymentMethod", "Coin", "Card", "VendingMachine", "Product"],
        "not_classes": ["Code", "Price"],
        "attributes": {"Product": ["code", "price"]},
        "methods": {"PaymentMethod": ["pay"], "VendingMachine": ["dispenseProduct"]},
        "realizes": [("Coin", "PaymentMethod"), ("Card", "PaymentMethod")],
        "interfaces": ["PaymentMethod"],
        "links": [("VendingMachine", "Product")],
    },
    {
        "name": "course-registration-lists",
        "text": (
            "1. Students register for sections.\n"
            "2. A section belongs to a course and has a room and a time slot.\n"
            "3. An instructor teaches up to four sections.\n"
            "4. A course has a code, a title and a credit value.\n"
            "5. A student has an id, a name and a major."
        ),
        "classes": ["Student", "Section", "Course", "Instructor"],
        "not_classes": ["Room", "TimeSlot", "Major"],
        "attributes": {"Course": ["code", "title"], "Student": ["id", "name", "major"]},
        "methods": {"Student": ["registerSection"]},
        "multiplicity": [("Instructor", "Section", "0..4")],
        "links": [("Section", "Course")],
    },
]
