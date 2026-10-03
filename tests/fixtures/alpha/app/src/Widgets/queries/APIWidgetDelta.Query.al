namespace Alpha.Widgets;

query 50003 "ALP API Widget Delta"
{
    QueryType = API;
    APIPublisher = 'example';
    APIGroup = 'alpha';
    APIVersion = 'v1.0';
    EntityName = 'widgetDelta';
    EntitySetName = 'widgetDelta';

    elements
    {
        dataitem(widget; "ALP Widget")
        {
            column(code; Code) { }
            column(lastModified; SystemModifiedAt) { }
        }
    }
}
