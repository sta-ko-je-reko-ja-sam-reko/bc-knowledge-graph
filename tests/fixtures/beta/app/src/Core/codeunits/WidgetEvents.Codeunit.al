namespace Beta.Core;

using Microsoft.Sales.Customer;

codeunit 50010 "BET Widget Events" implements "BET IPublisher", "BET ILogger"
{
    [EventSubscriber(ObjectType::Table, Database::Customer, OnAfterValidateEvent, 'Name', false, false)]
    local procedure OnAfterValidateCustomerName(var Rec: Record Customer)
    begin
        OnWidgetChanged(Rec."No.");
    end;

    [IntegrationEvent(false, false)]
    local procedure OnWidgetChanged(CustomerNo: Code[20])
    begin
    end;

    procedure Channel(): Text
    begin
        exit('widget.changed');
    end;
}
