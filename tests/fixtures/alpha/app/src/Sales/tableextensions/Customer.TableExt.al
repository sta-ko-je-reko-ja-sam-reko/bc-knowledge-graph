namespace Alpha.Sales;

using Microsoft.Sales.Customer;

tableextension 50000 "ALP Customer" extends Customer
{
    fields
    {
        field(50000; "ALP Widget Code"; Code[20])
        {
            Caption = 'Widget Code';
            TableRelation = "ALP Widget";
        }
    }
}
