from datetime import date, timedelta

# Returns current date - specified units
def subtractFromDate(days=0, weeks=0, months=0, years=0, vdate=''):
    if vdate == '':
        vdate = date.today()

    days += weeks * 7
    days += months * (365/12)
    days += years * 365
    
    return vdate - timedelta(days=days)