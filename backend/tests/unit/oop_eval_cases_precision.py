"""Easy / medium OOP tasks with the COMPLETE expected class list, so precision
(no invented classes) can be measured, not only recall. Written before any
fix driven by them; jotil/complex prose is intentionally left out.

- exact_classes: every class (and interface) a correct answer contains.
  Anything else the modeler produces counts as a false class.
- attributes / methods: members each class must have.
"""

PRECISION_CASES = [
    {
        "name": "p-library-simple",
        "text": (
            "A library has many books. A book has a title, an author and an ISBN. "
            "A member has a name and a member id. A member can borrow books and return books."
        ),
        "exact_classes": ["Library", "Book", "Member"],
        "attributes": {"Book": ["title", "author", "isbn"], "Member": ["name", "memberId"]},
        "methods": {"Member": ["borrowBook", "returnBook"]},
    },
    {
        "name": "p-car-rental",
        "text": (
            "A rental company owns many cars. A car has a plate number, a model and a daily price. "
            "A customer has a name and a driving license number. A customer can rent a car. "
            "A rental has a start date and an end date. Each rental belongs to one customer."
        ),
        "exact_classes": ["RentalCompany", "Car", "Customer", "Rental"],
        "attributes": {"Car": ["plateNumber", "model", "dailyPrice"], "Rental": ["startDate", "endDate"]},
        "methods": {"Customer": ["rentCar"]},
    },
    {
        "name": "p-employees-inheritance",
        "text": (
            "An employee has a name, an id and a salary. Managers and engineers are employees. "
            "A manager has a department name. An engineer has a skill level. "
            "A manager can approve leave requests. A leave request has a start date and a reason."
        ),
        "exact_classes": ["Employee", "Manager", "Engineer", "LeaveRequest"],
        "attributes": {"Employee": ["name", "id", "salary"], "Manager": ["departmentName"], "LeaveRequest": ["startDate", "reason"]},
        "methods": {"Manager": ["approveLeaveRequest"]},
        "inherits": [("Manager", "Employee"), ("Engineer", "Employee")],
    },
    {
        "name": "p-shapes-interface",
        "text": (
            "Drawable is an interface with a method draw. Shape is an abstract class. "
            "A shape has a color. Circles and squares are shapes. A circle has a radius. A square has a side length. "
            "Circles and squares implement Drawable."
        ),
        "exact_classes": ["Drawable", "Shape", "Circle", "Square"],
        "attributes": {"Shape": ["color"], "Circle": ["radius"], "Square": ["sideLength"]},
        "methods": {"Drawable": ["draw"], "Circle": ["draw"]},
        "inherits": [("Circle", "Shape"), ("Square", "Shape")],
        "realizes": [("Circle", "Drawable"), ("Square", "Drawable")],
    },
    {
        "name": "p-online-course",
        "text": (
            "An instructor creates courses. A course has a title, a price and a duration. "
            "A course contains many lessons. A lesson has a title and a video url. "
            "A student can enroll in a course. A student has a name and an email."
        ),
        "exact_classes": ["Instructor", "Course", "Lesson", "Student"],
        "attributes": {"Course": ["title", "price", "duration"], "Lesson": ["title", "videoUrl"], "Student": ["name", "email"]},
        "methods": {"Instructor": ["createCourse"]},
    },
    {
        "name": "p-pharmacy",
        "text": (
            "A pharmacist sells medicines to customers. A medicine has a name, a price and an expiry date. "
            "A customer has a name and a phone number. A pharmacist can update the stock of a medicine. "
            "Each sale has a date and a total amount."
        ),
        "exact_classes": ["Pharmacist", "Medicine", "Customer", "Sale"],
        "attributes": {"Medicine": ["name", "price", "expiryDate"], "Sale": ["date", "totalAmount"]},
        "methods": {"Pharmacist": ["sellMedicine"]},
    },
    {
        "name": "p-task-manager",
        "text": (
            "A user can create tasks. A task has a title, a due date and a priority. "
            "A task can be pending, in progress or done. A user can assign a task to another user. "
            "A user has a username and a password."
        ),
        "exact_classes": ["User", "Task"],
        "attributes": {"Task": ["title", "dueDate", "priority"], "User": ["username", "password"]},
        "methods": {"User": ["createTask"]},
    },
    {
        "name": "p-bank-simple",
        "text": (
            "A customer can open an account. An account has an account number and a balance. "
            "A customer can deposit money into an account and withdraw money from an account. "
            "A customer has a name and an address."
        ),
        "exact_classes": ["Customer", "Account"],
        "attributes": {"Account": ["accountNumber", "balance"], "Customer": ["name", "address"]},
        "methods": {"Customer": ["openAccount"]},
    },
    {
        "name": "p-cinema",
        "text": (
            "A cinema has several halls. Each hall has a hall number and a capacity. "
            "A movie has a title, a genre and a duration. A show is scheduled in a hall and plays a movie. "
            "A show has a start time. A customer buys tickets for a show. A ticket has a seat number and a price."
        ),
        "exact_classes": ["Cinema", "Hall", "Movie", "Show", "Customer", "Ticket"],
        "attributes": {"Hall": ["hallNumber", "capacity"], "Movie": ["title", "genre", "duration"], "Ticket": ["seatNumber", "price"]},
        "methods": {"Customer": ["buyTicket"]},
    },
    {
        "name": "p-blog",
        "text": (
            "An author writes articles. An article has a title, a body and a publish date. "
            "Readers can comment on articles. A comment has a text and a date. "
            "An author has a name and a bio."
        ),
        "exact_classes": ["Author", "Article", "Reader", "Comment"],
        "attributes": {"Article": ["title", "body", "publishDate"], "Comment": ["text", "date"], "Author": ["name", "bio"]},
        "methods": {"Author": ["writeArticle"]},
    },
    {
        "name": "p-smart-home",
        "text": (
            "A home has many devices. A device has a name and a status. Lights and thermostats are devices. "
            "A thermostat has a target temperature. A light has a brightness. "
            "A user can turn on a device and turn off a device."
        ),
        "exact_classes": ["Home", "Device", "Light", "Thermostat", "User"],
        "attributes": {"Device": ["name", "status"], "Thermostat": ["targetTemperature"], "Light": ["brightness"]},
        "methods": {"User": ["turnOnDevice", "turnOffDevice"]},
        "inherits": [("Light", "Device"), ("Thermostat", "Device")],
    },
    {
        "name": "p-premium-subtype",
        "text": (
            "A listener has a name and an email. A listener can play songs. A song has a title and a length. "
            "A premium listener can download songs."
        ),
        "exact_classes": ["Listener", "PremiumListener", "Song"],
        "attributes": {"Listener": ["name", "email"], "Song": ["title", "length"]},
        "methods": {"Listener": ["playSong"], "PremiumListener": ["downloadSong"]},
        "inherits": [("PremiumListener", "Listener")],
    },
]
