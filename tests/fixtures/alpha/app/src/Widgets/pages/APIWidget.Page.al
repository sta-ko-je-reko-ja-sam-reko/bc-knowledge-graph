namespace Alpha.Widgets;

page 50002 "ALP API Widget"
{
    PageType = API;
    APIPublisher = 'example';
    APIGroup = 'alpha';
    APIVersion = 'v1.0';
    EntityName = 'widget';
    EntitySetName = 'widgets';
    SourceTable = "ALP Widget";

    layout
    {
        area(Content)
        {
            repeater(Group)
            {
                field(systemId; Rec.SystemId) { }
                field(code; Rec.Code) { }
                field(description; Rec.Description) { }
                field(computed; ComputedText) { }
            }
        }
    }

    var
        ComputedText: Text;
}
