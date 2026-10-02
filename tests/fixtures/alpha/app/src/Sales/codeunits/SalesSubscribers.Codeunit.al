namespace Alpha.Sales;

using Microsoft.Sales.Customer;
using Microsoft.Sales.Posting;

codeunit 50000 "ALP Sales Subscribers"
{
    Access = Internal;

    [EventSubscriber(ObjectType::Codeunit, Codeunit::"Sales-Post", OnAfterPostSalesDoc, '', false, false)]
    local procedure OnAfterPostSalesDoc()
    begin
    end;

    [EventSubscriber(ObjectType::Table, Database::Customer, 'OnAfterValidateEvent', 'Name', false, false)]
    local procedure OnAfterValidateCustomerName(var Rec: Record Customer)
    var
        Widget: Record "ALP Widget";
    begin
        // Commented code must not count: Codeunit::"Ghost Codeunit"
        /* Neither must block comments: Record "Ghost Table" */
        Widget.Init();
        Message('It''s // not a comment');
    end;
}
