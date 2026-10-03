namespace Alpha.Test;

using Alpha.Widgets;

codeunit 60000 "ALP Widget Tests"
{
    Subtype = Test;

    [Test]
    procedure WidgetIsCreated()
    var
        Widget: Record "ALP Widget";
    begin
        Widget.Init();
    end;

    [Test]
    [HandlerFunctions('MessageHandler')]
    procedure WidgetHasCode()
    begin
    end;

    procedure NotATest()
    begin
    end;
}
