from cs50 import SQL # Harvard CS50 version of SQL (adapted from SQLite)
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# application configuration
app = Flask(__name__)

# ensure responses are not cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# Custom Filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem, rather than signed cookies
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    
    # Select each stock owned by the user
    portfolio_symbols = db.execute("SELECT shares, symbol FROM portfolio WHERE id = :id", id=session["user_id"])
    
    # Variable to store total of cash and shares
    total_cash = 0
    
    # Update stock prices and total
    for portfolio_symbol in portfolio_symbols:
        symbol = portfolio_symbol["symbol"]
        shares = portfolio_symbol["shares"]
        stock = lookup(symbol)
        total = shares * stock["price"]
        total_cash += total
        
        db.execute("UPDATE portfolio SET price=:price, total=:total WHERE id=:id AND symbol=:symbol",
                    price=usd(stock["price"]), total=usd(total), id=session["user_id"], symbol=symbol)
                    
    # Update user's cash in portfolio
    updated_cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    
    # Update total cash
    total_cash += updated_cash[0]["cash"]
    
    # Display portfolio in index.html
    updated_portfolio = db.execute("SELECT * FROM portfolio WHERE id=:id", id=session["user_id"])
    return render_template("index.html", stocks=updated_portfolio, cash=usd(updated_cash[0]["cash"]), total=usd(total_cash))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    
    if request.method == "POST":
        stock = lookup(request.form.get("symbol"))
        
        if not stock:
            return apology("Invalid stock symbol")
            
        # Ensure proper number of shares
        try:
            shares = int(request.form.get("shares"))
            if shares < 0:
                return apology("Number of shares must be positive")
                
        except:
            return apology("Number of shares must be positive")
            
        # Select cash from users database
        money = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        
        # Check if user has enough money to buy shares
        if not money or float(money[0]["cash"]) < stock["price"] * shares:
            return apology("Not enough money to buy stocks")
            
        # Update history
        db.execute("INSERT INTO histories (symbol, shares, price, id) VALUES(:symbol, :shares, :price, :id)",
                    symbol=stock["symbol"], shares=shares, price=usd(stock["price"]), id=session["user_id"])
                    
        # Update user cash
        db.execute("UPDATE users SET cash = cash - :purchase WHERE id = :id", id=session["user_id"], purchase=stock["price"] * float(shares))
    
        # Select user shares of that symbol
        user_shares = db.execute("SELECT shares FROM portfolio WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=stock["symbol"])
    
        # Create new stock object if user does not have shares of that symbol
        if not user_shares:
            db.execute("INSERT INTO portfolio (name, shares, price, total, symbol, id) VALUES(:name, :shares, :price, :total, :symbol, :id)",
            name=stock["name"], shares=shares, price=usd(stock["price"]), total=usd(shares * stock["price"]), symbol=stock["symbol"], id=session["user_id"])
    
        # Else increment shares count
        else:
            shares_total = user_shares[0]["shares"] + shares
            db.execute("UPDATE portfolio SET shares=:shares WHERE id=:id AND symbol=:symbol", shares=shares_total, id=session["user_id"], symbol=stock["symbol"])

        # Return to index
        return redirect(url_for("index"))
        
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    
    histories = db.execute("SELECT * from histories WHERE id=:id", id=session["user_id"])
    
    return render_template("history.html", histories=histories)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    if request.method == "POST":
        
        # Check for the requested symbol
        rows = lookup(request.form.get("symbol"))
        
        # If symbol not found, return apology
        if not rows:
            return apology("Invalid stock symbol")
            
        # If symbol found, return the price of the symbol(stock) in the quoted.html template
        return render_template("quoted.html", stock=rows)
        
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    if request.method == "POST":
        
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username")
            
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password")
            
        # Ensure password and password again are same
        elif request.form.get("password") != request.form.get("passwordagain"):
            return apology("Password does not match")
            
        # Insert the new user data into users table and store the password as hash
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                            username=request.form.get("username"), hash=pwd_context.encrypt(request.form.get("password")))
                            
        # If failure, then return apology
        if not result:
            return apology("Username already exist")
            
        # Remember logged in user
        session["user_id"] = result
        
        # Redirect user to homepage
        return redirect(url_for("index"))
        
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    
    if request.method == "POST":
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("Invalid stock symbol")
        
        # Ensure proper number of shares
        try:
            shares = int(request.form.get("shares"))
            if shares < 0:
                return apology("Number of shares must be positive")
        except:
            return apology("Number of shares must be positive")
        
        # Select the shares of the user
        user_shares = db.execute("SELECT shares FROM portfolio WHERE id = :id AND symbol=:symbol", id=session["user_id"], symbol=stock["symbol"])
        
        # Check if there are enough shares to sell
        if not user_shares or int(user_shares[0]["shares"]) < shares:
            return apology("Not enough shares to sell")
        
        # Update history
        db.execute("INSERT INTO histories (symbol, shares, price, id) VALUES(:symbol, :shares, :price, :id)",
                    symbol=stock["symbol"], shares=-shares, price=usd(stock["price"]), id=session["user_id"])
                       
        # Update user's cash              
        db.execute("UPDATE users SET cash = cash + :purchase WHERE id = :id", id=session["user_id"], purchase=stock["price"] * float(shares))
                        
        # Decrement the shares count
        shares_total = user_shares[0]["shares"] - shares
        
        # Delete shares from portfolio, if total shares are 0
        if shares_total == 0:
            db.execute("DELETE FROM portfolio WHERE id=:id AND symbol=:symbol", id=session["user_id"], symbol=stock["symbol"])
        
        # Else, update number of shares in the portfolio
        else:
            db.execute("UPDATE portfolio SET shares=:shares WHERE id=:id AND symbol=:symbol", shares=shares_total, id=session["user_id"], symbol=stock["symbol"])
        
        # Return to index
        return redirect(url_for("index"))
        
    else:
        return render_template("sell.html")
        
@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """Add additional cash."""
    
    if request.method == "POST":
        
        try:
            add_cash = int(request.form.get("add_cash"))
            if add_cash < 0:
                return apology("Enter a positive amount")
            elif add_cash > 10000:
                return apology("Cannot add more than $10,000 at once")
        except:
            return apology("Enter a positive amount")
            
        # Update user's cash             
        db.execute("UPDATE users SET cash = cash + :add_cash WHERE id = :id", add_cash=add_cash, id=session["user_id"])
        
        # Return to index
        return apology("Cash is loaded in the account")
    
    else:
        return render_template("add_cash.html")