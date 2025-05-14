from src.utils import round_to_0_05,roundof

def second_set_of_gtt_orders_creation(entered_price,lotsize,qty):
    # Calculate trigger prices (target levels)
    trigger_price = round_to_0_05(entered_price * 1.05)

    # Calculate limit prices (slightly below trigger)
    limit_price = round_to_0_05(trigger_price * 0.99)

    # Stop-loss values
    sl_price = round_to_0_05(entered_price * 0.942)  ## This is SL limit price with some gap
    sl_trigger_price = round_to_0_05(entered_price * 0.95)  ## This actual exit price

    # Quantity splits
    ##lotsize = 500   #### remove this in live.
    qty1 = int((qty * 0.40) * lotsize)
    qty2 = int((qty * 0.40) * lotsize)
    qty3 = int((qty * 0.20) * lotsize)

    return trigger_price,limit_price,sl_price,sl_trigger_price,qty1,qty2,qty3

def third_orders_assumption_values():

    assumption_value = roundof(1.2)
    assumption_third_order = roundof(1.4)
    modified_sl_order2= 0.1
    modified_sl_order3 = 0.2

    return assumption_value,assumption_third_order,modified_sl_order3,modified_sl_order2